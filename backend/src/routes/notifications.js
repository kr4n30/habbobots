import { Router } from 'express';
import { getDB }       from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.use(requireAuth);

// ── GET /notifications ────────────────────────────
// Lista las notificaciones del usuario (no leídas primero)
router.get('/', (req, res) => {
  const db    = getDB();
  const limit = Math.min(parseInt(req.query.limit) || 30, 100);

  const notifs = db.prepare(`
    SELECT id, type, title, message, data, read, created_at
    FROM notifications
    WHERE user_id = ?
    ORDER BY read ASC, created_at DESC
    LIMIT ?
  `).all(req.user.id, limit);

  const unreadCount = db.prepare(
    `SELECT COUNT(*) as n FROM notifications WHERE user_id = ? AND read = 0`
  ).get(req.user.id).n;

  res.json({ notifications: notifs, unreadCount });
});

// ── POST /notifications/:id/read ──────────────────
router.post('/:id/read', (req, res) => {
  const db = getDB();
  const n  = db.prepare('SELECT id FROM notifications WHERE id = ? AND user_id = ?')
               .get(req.params.id, req.user.id);

  if (!n) return res.status(404).json({ error: 'Notificación no encontrada' });

  db.prepare(`UPDATE notifications SET read = 1 WHERE id = ?`).run(req.params.id);
  res.json({ ok: true });
});

// ── POST /notifications/read-all ──────────────────
router.post('/read-all', (req, res) => {
  const db = getDB();
  db.prepare(`UPDATE notifications SET read = 1 WHERE user_id = ? AND read = 0`)
    .run(req.user.id);
  res.json({ ok: true });
});

// ── DELETE /notifications/:id ─────────────────────
router.delete('/:id', (req, res) => {
  const db = getDB();
  const n  = db.prepare('SELECT id FROM notifications WHERE id = ? AND user_id = ?')
               .get(req.params.id, req.user.id);

  if (!n) return res.status(404).json({ error: 'Notificación no encontrada' });

  db.prepare('DELETE FROM notifications WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

export default router;
