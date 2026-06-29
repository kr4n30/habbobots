// ───────────────────────────────────────────────
//  HabboBots — Cron Jobs
//  • Cada hora: email 24h antes de expirar bots
//  • Cada 5min: pings VPS y Discord alert si cae
//  • Cada hora: push notification de bots expirando
// ───────────────────────────────────────────────
import { getDB }                 from '../database/init.js';
import { sendBotExpiryEmail }    from './email.js';
import { discordError, sendDiscord } from './discord.js';
import { sendPushToUser }        from './push.js';

let lastVpsOnline = true;

// ── Helper: ejecutar tarea con logs ──────────────────────────────────────────
function runJob(name, fn) {
  fn().catch(err => console.error(`[CRON][${name}]`, err.message));
}

// ══════════════════════════════════════════════════════════════════════════════
//  JOB 1 — Email + push 24h antes de expirar bots  (cada 60 min)
// ══════════════════════════════════════════════════════════════════════════════
async function jobBotExpiry() {
  const db = getDB();

  // Bots que expiran entre ahora+23h y ahora+25h y no se ha enviado aviso
  const expiring = db.prepare(`
    SELECT b.id, b.name, b.user_id, b.expires_at,
           u.email, u.username
    FROM bots b
    JOIN users u ON u.id = b.user_id
    WHERE b.expires_at BETWEEN datetime('now', '+23 hours')
                           AND datetime('now', '+25 hours')
      AND (b.expiry_notified IS NULL OR b.expiry_notified = 0)
      AND b.status != 'offline'
  `).all();

  for (const bot of expiring) {
    try {
      await sendBotExpiryEmail(bot.email, bot.username, bot.name, bot.expires_at);
      console.log(`[CRON] Email expiración enviado → ${bot.email} (bot: ${bot.name})`);
    } catch (e) {
      console.warn(`[CRON] Email expiración falló:`, e.message);
    }

    // Push notification
    try {
      await sendPushToUser(bot.user_id, {
        title: `⚠️ Bot "${bot.name}" expira pronto`,
        body:  'Tu bot expirará en menos de 24 horas. ¡Renuévalo ahora!',
        url:   '/bots',
      });
    } catch {}

    // Marcar como notificado (ignorar si columna no existe)
    try {
      db.prepare("UPDATE bots SET expiry_notified=1 WHERE id=?").run(bot.id);
    } catch {}
  }

  if (expiring.length) {
    console.log(`[CRON] jobBotExpiry: ${expiring.length} avisos enviados`);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
//  JOB 2 — Monitor VPS + Discord alert  (cada 5 min)
// ══════════════════════════════════════════════════════════════════════════════
async function jobVpsMonitor() {
  const VPS_URL = process.env.BOT_VPS_URL || 'http://localhost:5001';
  let online = false;
  try {
    const r = await fetch(`${VPS_URL}/health`, { signal: AbortSignal.timeout(4000) });
    online = r.ok;
  } catch {}

  if (!online && lastVpsOnline) {
    // Acaba de caerse → alerta
    await discordError('Bot Manager (5001)', 'El bot manager no responde. Posible caída del VPS.').catch(() => {});
    try {
      // Registrar incidencia
      const db = getDB();
      db.prepare("INSERT INTO bot_incidents (title) VALUES (?)").run('Bot Manager caído (sin respuesta en /health)');
    } catch {}
    console.error('[CRON] ⚠️  VPS bot manager CAÍDO — Discord alert enviado');
  }

  if (online && !lastVpsOnline) {
    // Se recuperó
    await sendDiscord({
      title:       '✅ Bot Manager recuperado',
      description: 'El bot manager en el VPS vuelve a responder correctamente.',
      color:       0x00ffa3,
      timestamp:   new Date().toISOString(),
    }, ['DISCORD_WEBHOOK_URL']).catch(() => {});
    try {
      const db = getDB();
      db.prepare("INSERT INTO bot_incidents (title, resolved) VALUES (?,1)").run('Bot Manager recuperado');
    } catch {}
    console.log('[CRON] ✅  VPS bot manager RECUPERADO');
  }

  lastVpsOnline = online;
}

// ══════════════════════════════════════════════════════════════════════════════
//  JOB 3 — Limpiar bots expirados (cada 6h)
// ══════════════════════════════════════════════════════════════════════════════
async function jobCleanExpired() {
  const db = getDB();
  const expired = db.prepare(
    "SELECT id FROM bots WHERE expires_at < datetime('now', '-1 days') AND status != 'offline'"
  ).all();

  for (const bot of expired) {
    try {
      await fetch(`${process.env.BOT_VPS_URL || 'http://localhost:5001'}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'destroy', botId: bot.id }),
        signal: AbortSignal.timeout(3000),
      });
    } catch {}
    db.prepare("UPDATE bots SET status='offline' WHERE id=?").run(bot.id);
  }

  if (expired.length) console.log(`[CRON] jobCleanExpired: ${expired.length} bots marcados offline`);
}

// ══════════════════════════════════════════════════════════════════════════════
//  START — Registrar todos los jobs
// ══════════════════════════════════════════════════════════════════════════════
export function startCron() {
  // Migrar columna si no existe
  try {
    const db = getDB();
    db.exec('ALTER TABLE bots ADD COLUMN expiry_notified INTEGER NOT NULL DEFAULT 0');
  } catch {}

  // Job 1: cada 60 minutos
  runJob('BotExpiry', jobBotExpiry);
  setInterval(() => runJob('BotExpiry', jobBotExpiry), 60 * 60 * 1000);

  // Job 2: cada 5 minutos
  runJob('VpsMonitor', jobVpsMonitor);
  setInterval(() => runJob('VpsMonitor', jobVpsMonitor), 5 * 60 * 1000);

  // Job 3: cada 6 horas
  runJob('CleanExpired', jobCleanExpired);
  setInterval(() => runJob('CleanExpired', jobCleanExpired), 6 * 60 * 60 * 1000);

  console.log('⏰ Cron jobs iniciados (BotExpiry 60m | VpsMonitor 5m | CleanExpired 6h)');
}
