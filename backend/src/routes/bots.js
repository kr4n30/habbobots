import { Router } from 'express';
import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';
import { chargeCredits } from '../services/credits.js';
import { sendVPSCommand } from '../services/vps.js';

const router = Router();
router.use(requireAuth);

const SUPPORTED_HOTELS = ['es', 'com', 'com.br', 'de', 'fi', 'it', 'nl', 'tr'];
const BOT_COST_PER_MONTH = 60; // credits

// ── GET /bots ─────────────────────────────────────
router.get('/', (req, res) => {
  const db   = getDB();
  const bots = db.prepare('SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC').all(req.user.id);
  res.json({ bots });
});

// ── GET /bots/:id ─────────────────────────────────
router.get('/:id', (req, res) => {
  const db  = getDB();
  const bot = db.prepare('SELECT * FROM bots WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
  if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });
  res.json({ bot });
});

// ── POST /bots ────────────────────────────────────
router.post('/', async (req, res, next) => {
  try {
    const { name, hotel, room } = req.body;

    if (!name || !hotel) return res.status(400).json({ error: 'name y hotel son obligatorios' });
    if (!SUPPORTED_HOTELS.includes(hotel)) {
      return res.status(400).json({ error: `Hotel no soportado. Válidos: ${SUPPORTED_HOTELS.join(', ')}` });
    }

    const db   = getDB();
    const user = db.prepare('SELECT credits FROM users WHERE id = ?').get(req.user.id);

    if (user.credits < BOT_COST_PER_MONTH) {
      return res.status(402).json({
        error: `Créditos insuficientes. Necesitas ${BOT_COST_PER_MONTH}, tienes ${user.credits}.`,
      });
    }

    // Charge credits
    await chargeCredits(req.user.id, BOT_COST_PER_MONTH, `Bot "${name}" en habbo.${hotel}`);

    const id = uuid();
    const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

    db.prepare(`
      INSERT INTO bots (id, user_id, name, hotel, room, status, cost_per_month, expires_at)
      VALUES (?, ?, ?, ?, ?, 'offline', ?, ?)
    `).run(id, req.user.id, name, hotel, room || null, BOT_COST_PER_MONTH, expiresAt);

    // Notify VPS to spawn the bot
    try {
      await sendVPSCommand('spawn', { botId: id, name, hotel, room });
    } catch {
      // VPS might not be configured in dev — don't fail the request
    }

    const bot = db.prepare('SELECT * FROM bots WHERE id = ?').get(id);
    res.status(201).json({ bot });
  } catch (err) { next(err); }
});

// ── PATCH /bots/:id ───────────────────────────────
router.patch('/:id', async (req, res, next) => {
  try {
    const { name, room } = req.body;
    const db  = getDB();
    const bot = db.prepare('SELECT * FROM bots WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });

    const updates = {};
    if (name) updates.name = name;
    if (room !== undefined) updates.room = room;

    if (Object.keys(updates).length > 0) {
      const setClause = Object.keys(updates).map(k => `${k} = ?`).join(', ');
      db.prepare(`UPDATE bots SET ${setClause}, updated_at = datetime('now') WHERE id = ?`)
        .run(...Object.values(updates), bot.id);
    }

    const updated = db.prepare('SELECT * FROM bots WHERE id = ?').get(bot.id);
    res.json({ bot: updated });
  } catch (err) { next(err); }
});

// ── POST /bots/:id/start ──────────────────────────
router.post('/:id/start', async (req, res, next) => {
  try {
    const db  = getDB();
    const bot = db.prepare('SELECT * FROM bots WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });

    await sendVPSCommand('start', { botId: bot.id });
    db.prepare("UPDATE bots SET status = 'online', updated_at = datetime('now') WHERE id = ?").run(bot.id);

    res.json({ message: 'Bot iniciado', status: 'online' });
  } catch (err) { next(err); }
});

// ── POST /bots/:id/stop ───────────────────────────
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

// ── DELETE /bots/:id ──────────────────────────────
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
