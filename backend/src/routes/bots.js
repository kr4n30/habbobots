import { Router } from 'express';
import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';
import { chargeCredits } from '../services/credits.js';
import { sendVPSCommand } from '../services/vps.js';

const router = Router();
router.use(requireAuth);

const SUPPORTED_HOTELS = ['es', 'com', 'com.br', 'de', 'fi', 'it', 'nl', 'tr', 'fr'];

// ── Planes de duración ────────────────────────────────────────────────────────
// credits = coste en créditos | days = duración | hours = para el VPS
const DURATION_PLANS = {
  '1d':  { label: '1 día',    days: 1,   hours: 24,   credits: 5   },
  '3d':  { label: '3 días',   days: 3,   hours: 72,   credits: 12  },
  '7d':  { label: '1 semana', days: 7,   hours: 168,  credits: 25  },
  '1m':  { label: '1 mes',    days: 30,  hours: 720,  credits: 60  },
  '3m':  { label: '3 meses',  days: 90,  hours: 2160, credits: 150 },
};

// ── GET /bots ─────────────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  const db   = getDB();
  const bots = db.prepare('SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC').all(req.user.id);
  res.json({ bots, plans: DURATION_PLANS });
});

// ── GET /bots/plans — devuelve los planes disponibles ────────────────────────
router.get('/plans', (_req, res) => {
  res.json({ plans: DURATION_PLANS });
});

// ── GET /bots/:id ─────────────────────────────────────────────────────────────
router.get('/:id', (req, res) => {
  const db  = getDB();
  const bot = db.prepare('SELECT * FROM bots WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
  if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });
  res.json({ bot });
});

// ── POST /bots — contratar uno o varios bots ─────────────────────────────────
router.post('/', async (req, res, next) => {
  try {
    const { name, hotel, room, duration = '1m', quantity = 1 } = req.body;

    if (!name || !hotel)
      return res.status(400).json({ error: 'name y hotel son obligatorios' });
    if (!SUPPORTED_HOTELS.includes(hotel))
      return res.status(400).json({ error: `Hotel no soportado. Válidos: ${SUPPORTED_HOTELS.join(', ')}` });

    const plan = DURATION_PLANS[duration];
    if (!plan)
      return res.status(400).json({
        error: `Duración no válida. Opciones: ${Object.keys(DURATION_PLANS).join(', ')}`,
      });

    const qty = Math.max(1, Math.min(50, parseInt(quantity) || 1));
    const totalCredits = plan.credits * qty;

    const db   = getDB();
    const user = db.prepare('SELECT credits FROM users WHERE id = ?').get(req.user.id);

    if (user.credits < totalCredits)
      return res.status(402).json({
        error: `Créditos insuficientes. Necesitas ${totalCredits} para ${qty} bot${qty>1?'s':''} (${plan.label}), tienes ${user.credits}.`,
      });

    chargeCredits(
      req.user.id,
      totalCredits,
      `${qty} bot${qty>1?'s':''} en habbo.${hotel} (${plan.label})`
    );

    const expiresAt = new Date(Date.now() + plan.days * 24 * 60 * 60 * 1000).toISOString();
    const createdBots = [];

    for (let i = 0; i < qty; i++) {
      const id       = uuid();
      const botName  = qty > 1 ? `${name}_${i + 1}` : name;

      db.prepare(`
        INSERT INTO bots (id, user_id, name, hotel, room, status, cost_per_month, expires_at)
        VALUES (?, ?, ?, ?, ?, 'offline', ?, ?)
      `).run(id, req.user.id, botName, hotel, room || null, plan.credits, expiresAt);

      try {
        db.prepare(`UPDATE bots SET duration_label = ? WHERE id = ?`).run(plan.label, id);
      } catch { /* columna puede no existir aún en DBs viejas */ }

      // Notificar al bot manager en el VPS
      try {
        await sendVPSCommand('spawn', {
          botId:         id,
          name:          botName,
          hotel,
          room,
          durationHours: plan.hours,
          userId:        req.user.id,
        });
      } catch (vpsErr) {
        console.warn(`[VPS] spawn #${i+1} falló (bot queda en offline):`, vpsErr.message);
      }

      createdBots.push(db.prepare('SELECT * FROM bots WHERE id = ?').get(id));
    }

    // Actualizar stats del usuario
    db.prepare(`
      INSERT INTO user_stats (user_id, bots_used) VALUES (?, ?)
      ON CONFLICT(user_id) DO UPDATE SET bots_used = bots_used + ?, updated_at = datetime('now')
    `).run(req.user.id, qty, qty);

    res.status(201).json({
      bots: createdBots,
      bot:  createdBots[0],   // compatibilidad con frontend que sólo lee .bot
      plan,
      quantity: qty,
      totalCredits,
    });
  } catch (err) { next(err); }
});

// ── PATCH /bots/:id ───────────────────────────────────────────────────────────
router.patch('/:id', (req, res, next) => {
  try {
    const { name, room } = req.body;
    const db  = getDB();
    const bot = db.prepare('SELECT * FROM bots WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });

    const updates = [];
    const values  = [];
    if (name)              { updates.push('name = ?'); values.push(name); }
    if (room !== undefined){ updates.push('room = ?'); values.push(room); }

    if (updates.length > 0) {
      db.prepare(`UPDATE bots SET ${updates.join(', ')}, updated_at = datetime('now') WHERE id = ?`)
        .run(...values, bot.id);
    }

    const updated = db.prepare('SELECT * FROM bots WHERE id = ?').get(bot.id);
    res.json({ bot: updated });
  } catch (err) { next(err); }
});

// ── POST /bots/:id/start ──────────────────────────────────────────────────────
router.post('/:id/start', async (req, res, next) => {
  try {
    const db  = getDB();
    const bot = db.prepare('SELECT * FROM bots WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });

    if (bot.expires_at && new Date(bot.expires_at) < new Date())
      return res.status(402).json({ error: 'El bot ha expirado. Contrátalo de nuevo.' });

    await sendVPSCommand('start', { botId: bot.id });
    db.prepare("UPDATE bots SET status = 'online', updated_at = datetime('now') WHERE id = ?").run(bot.id);
    res.json({ message: 'Bot iniciado', status: 'online' });
  } catch (err) { next(err); }
});

// ── POST /bots/:id/stop ───────────────────────────────────────────────────────
router.post('/:id/stop', async (req, res, next) => {
  try {
    const db  = getDB();
    const bot = db.prepare('SELECT * FROM bots WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });

    await sendVPSCommand('stop', { botId: bot.id });
    db.prepare("UPDATE bots SET status = 'offline', updated_at = datetime('now') WHERE id = ?").run(bot.id);
    res.json({ message: 'Bot detenido', status: 'offline' });
  } catch (err) { next(err); }
});

// ── POST /bots/:id/action — controla el bot vía VPS ──────────────────────────
router.post('/:id/action', async (req, res, next) => {
  try {
    const db  = getDB();
    const bot = db.prepare('SELECT * FROM bots WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });

    if (bot.expires_at && new Date(bot.expires_at) < new Date())
      return res.status(402).json({ error: 'El bot ha expirado.' });

    const { action, params = {} } = req.body;
    if (!action) return res.status(400).json({ error: 'Falta action' });

    let result, ok = true;
    try {
      result = await sendVPSCommand('action', { botId: bot.id, action, params });
    } catch (e) {
      result = { error: e.message }; ok = false;
    }

    // Guardar en bot_logs
    try {
      db.prepare(`
        INSERT INTO bot_logs (bot_id, user_id, action, params, result, ok)
        VALUES (?, ?, ?, ?, ?, ?)
      `).run(bot.id, req.user.id, action, JSON.stringify(params), JSON.stringify(result), ok ? 1 : 0);
    } catch {}

    if (!ok) return res.status(400).json({ error: result.error || 'Error en el VPS' });
    res.json({ ok: true, result });
  } catch (err) { next(err); }
});

// ── GET /bots/:id/logs — historial de acciones ───────────────────────────────
router.get('/:id/logs', (req, res) => {
  const db  = getDB();
  const bot = db.prepare('SELECT id FROM bots WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
  if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });

  const limit = Math.min(200, parseInt(req.query.limit) || 50);
  const logs  = db.prepare(`
    SELECT * FROM bot_logs WHERE bot_id = ? ORDER BY created_at DESC LIMIT ?
  `).all(bot.id, limit);

  res.json({ logs: logs.map(l => ({
    ...l,
    params: l.params ? JSON.parse(l.params) : null,
    result: l.result ? JSON.parse(l.result) : null,
  }))});
});

// ── DELETE /bots/:id ──────────────────────────────────────────────────────────
router.delete('/:id', async (req, res, next) => {
  try {
    const db  = getDB();
    const bot = db.prepare('SELECT * FROM bots WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });

    try { await sendVPSCommand('destroy', { botId: bot.id }); } catch {}
    db.prepare('DELETE FROM bots WHERE id = ?').run(bot.id);
    res.json({ message: 'Bot eliminado' });
  } catch (err) { next(err); }
});

export default router;
