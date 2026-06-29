import { Router } from 'express';
import { v4 as uuid } from 'uuid';
import { getDB }       from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();

// ── GET /reviews/product/:id — Público ───────────
router.get('/product/:id', (req, res) => {
  const db  = getDB();
  const reviews = db.prepare(`
    SELECT r.id, r.rating, r.comment, r.created_at, u.username
    FROM reviews r JOIN users u ON u.id=r.user_id
    WHERE r.product_id=?
    ORDER BY r.created_at DESC LIMIT 30
  `).all(req.params.id);

  const stats = db.prepare(`
    SELECT ROUND(AVG(rating),1) as avg, COUNT(*) as total
    FROM reviews WHERE product_id=?
  `).get(req.params.id);

  res.json({ reviews, avg: stats.avg || 0, total: stats.total });
});

router.use(requireAuth);

// ── GET /reviews/my ───────────────────────────────
router.get('/my', (req, res) => {
  const db = getDB();
  const reviews = db.prepare(`
    SELECT r.*, p.name as product_name
    FROM reviews r JOIN products p ON p.id=r.product_id
    WHERE r.user_id=?
    ORDER BY r.created_at DESC
  `).all(req.user.id);
  res.json({ reviews });
});

// ── POST /reviews ─────────────────────────────────
router.post('/', (req, res) => {
  const { order_id, rating, comment } = req.body;

  if (!order_id || !rating)
    return res.status(400).json({ error: 'order_id y rating son obligatorios' });
  if (rating < 1 || rating > 5)
    return res.status(400).json({ error: 'Rating debe ser entre 1 y 5' });

  const db    = getDB();
  const order = db.prepare(`
    SELECT * FROM service_orders WHERE id=? AND user_id=? AND status='completed'
  `).get(order_id, req.user.id);

  if (!order)
    return res.status(400).json({ error: 'Solo puedes reseñar pedidos completados tuyos' });

  const existing = db.prepare('SELECT id FROM reviews WHERE order_id=? AND user_id=?').get(order_id, req.user.id);
  if (existing)
    return res.status(409).json({ error: 'Ya has dejado una reseña para este pedido' });

  const id = uuid();
  db.prepare(`
    INSERT INTO reviews (id, user_id, order_id, product_id, rating, comment)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(id, req.user.id, order_id, order.product_id, parseInt(rating), comment?.trim() || null);

  const review = db.prepare('SELECT * FROM reviews WHERE id=?').get(id);
  res.status(201).json({ review });
});

// ── DELETE /reviews/:id ───────────────────────────
router.delete('/:id', (req, res) => {
  const db = getDB();
  const r  = db.prepare('SELECT * FROM reviews WHERE id=? AND user_id=?').get(req.params.id, req.user.id);
  if (!r) return res.status(404).json({ error: 'Reseña no encontrada' });
  db.prepare('DELETE FROM reviews WHERE id=?').run(req.params.id);
  res.json({ message: 'Reseña eliminada' });
});

export default router;
