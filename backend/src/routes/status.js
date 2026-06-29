// ───────────────────────────────────────────────
//  HabboBots — Public Status Endpoint
//  GET /status  (sin auth)
// ───────────────────────────────────────────────
import { Router } from 'express';
import { getDB }  from '../database/init.js';

const router = Router();
const START  = Date.now();

function fmt(ms) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 0) return `${d}d ${h % 24}h`;
  if (h > 0) return `${h}h ${m % 60}m`;
  if (m > 0) return `${m}m`;
  return `${s}s`;
}

async function pingUrl(url, timeout = 3000) {
  const t0 = Date.now();
  try {
    const r = await fetch(`${url}/health`, { signal: AbortSignal.timeout(timeout) });
    return { online: r.ok, latency: Date.now() - t0 };
  } catch {
    return { online: false, latency: null };
  }
}

router.get('/', async (_req, res) => {
  const db = getDB();

  // Comprobar servicios Python en paralelo
  const VPS_URL = process.env.BOT_VPS_URL || 'http://localhost:5001';
  const GUI_URL = process.env.BOT_GUI_URL || 'http://localhost:5000';

  const [vps, gui] = await Promise.all([
    pingUrl(VPS_URL),
    pingUrl(GUI_URL),
  ]);

  // BD siempre online si llegamos aquí
  let dbOnline = true;
  try { db.prepare('SELECT 1').get(); } catch { dbOnline = false; }

  const services = [
    { id: 'backend',     status: 'online', latency: null }, // estamos respondiendo → online
    { id: 'bot_manager', status: vps.online ? 'online' : 'offline', latency: vps.latency },
    { id: 'web_gui',     status: gui.online ? 'online' : 'offline', latency: gui.latency },
    { id: 'database',    status: dbOnline   ? 'online' : 'offline', latency: null },
  ];

  // Stats rápidas
  let stats = { activeBots: 0, ordersToday: 0, uptime: fmt(Date.now() - START) };
  try {
    stats.activeBots  = db.prepare("SELECT COUNT(*) as n FROM bots WHERE status='online'").get().n;
    stats.ordersToday = db.prepare(
      "SELECT COUNT(*) as n FROM service_orders WHERE date(created_at)=date('now')"
    ).get().n;
  } catch {}

  // Incidencias recientes (últimas 24h desde bot_incidents si existe)
  let incidents = [];
  try {
    incidents = db.prepare(
      "SELECT * FROM bot_incidents WHERE at > datetime('now','-24 hours') ORDER BY at DESC LIMIT 10"
    ).all();
  } catch {}

  res.json({ services, stats, incidents, generatedAt: new Date().toISOString() });
});

export default router;
