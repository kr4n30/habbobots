// ───────────────────────────────────────────────
//  HabboBots — Push Subscription Routes
//  POST /push/subscribe
//  POST /push/unsubscribe
//  GET  /push/vapid-key
// ───────────────────────────────────────────────
import { Router }          from 'express';
import { getDB }           from '../database/init.js';
import { requireAuth }     from '../middleware/auth.js';
import { getVapidPublicKey } from '../services/push.js';

const router = Router();

// ── GET /push/vapid-key (público) ─────────────
router.get('/vapid-key', (_req, res) => {
  const key = getVapidPublicKey();
  if (!key) return res.status(503).json({ error: 'Push no configurado (falta VAPID_PUBLIC_KEY)' });
  res.json({ publicKey: key });
});

// ── POST /push/subscribe ──────────────────────
router.post('/subscribe', requireAuth, (req, res) => {
  const { endpoint, keys } = req.body;
  if (!endpoint || !keys?.p256dh || !keys?.auth)
    return res.status(400).json({ error: 'Suscripción inválida' });

  const db = getDB();
  try {
    db.prepare(`
      INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(endpoint) DO UPDATE SET user_id=?, p256dh=?, auth=?
    `).run(
      req.user.id, endpoint, keys.p256dh, keys.auth,
      req.user.id, keys.p256dh, keys.auth,
    );
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── POST /push/unsubscribe ────────────────────
router.post('/unsubscribe', requireAuth, (req, res) => {
  const { endpoint } = req.body;
  const db = getDB();
  if (endpoint) {
    db.prepare('DELETE FROM push_subscriptions WHERE endpoint = ? AND user_id = ?').run(endpoint, req.user.id);
  } else {
    db.prepare('DELETE FROM push_subscriptions WHERE user_id = ?').run(req.user.id);
  }
  res.json({ ok: true });
});

export default router;
