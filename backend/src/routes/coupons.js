// ───────────────────────────────────────────────
//  HabboBots — Coupons Routes
//  POST /coupons/validate  → validar cupón (público)
//  GET  /coupons           → listar (admin)
//  POST /coupons           → crear (admin)
//  PATCH /coupons/:id      → editar (admin)
//  DELETE /coupons/:id     → eliminar (admin)
// ───────────────────────────────────────────────

import { Router } from 'express';
import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';
import { requireAuth, requireAdmin } from '../middleware/auth.js';

const router = Router();

// ── POST /coupons/validate ─────────────────────
// Verifica el cupón y devuelve el descuento (sin aplicarlo aún)
router.post('/validate', requireAuth, (req, res) => {
  const { code } = req.body;
  if (!code) return res.status(400).json({ error: 'Código requerido' });

  const db     = getDB();
  const coupon = db.prepare(`
    SELECT * FROM coupons
    WHERE UPPER(code) = UPPER(?)
    AND active = 1
    AND (max_uses IS NULL OR uses < max_uses)
    AND (expires_at IS NULL OR expires_at > datetime('now'))
  `).get(code.trim());

  if (!coupon) return res.status(404).json({ error: 'Cupón inválido o expirado' });

  res.json({
    valid:       true,
    code:        coupon.code,
    discountPct: coupon.discount_pct,
  });
});

// ── GET /coupons (admin) ───────────────────────
router.get('/', requireAdmin, (req, res) => {
  const db      = getDB();
  const coupons = db.prepare('SELECT * FROM coupons ORDER BY created_at DESC').all();
  res.json({ coupons });
});

// ── POST /coupons (admin) ──────────────────────
router.post('/', requireAdmin, (req, res) => {
  const { code, discount_pct = 10, max_uses, expires_at } = req.body;
  if (!code) return res.status(400).json({ error: 'code es obligatorio' });
  if (discount_pct < 1 || discount_pct > 100)
    return res.status(400).json({ error: 'discount_pct debe estar entre 1 y 100' });

  const db = getDB();
  const id = uuid();
  try {
    db.prepare(`
      INSERT INTO coupons (id, code, discount_pct, max_uses, expires_at)
      VALUES (?, UPPER(?), ?, ?, ?)
    `).run(id, code.trim(), parseInt(discount_pct), max_uses ? parseInt(max_uses) : null, expires_at || null);
  } catch {
    return res.status(409).json({ error: 'El código ya existe' });
  }
  const coupon = db.prepare('SELECT * FROM coupons WHERE id = ?').get(id);
  res.status(201).json({ coupon });
});

// ── PATCH /coupons/:id (admin) ─────────────────
router.patch('/:id', requireAdmin, (req, res) => {
  const db = getDB();
  const { discount_pct, max_uses, active, expires_at } = req.body;
  const existing = db.prepare('SELECT * FROM coupons WHERE id = ?').get(req.params.id);
  if (!existing) return res.status(404).json({ error: 'Cupón no encontrado' });

  db.prepare(`
    UPDATE coupons SET
      discount_pct = COALESCE(?, discount_pct),
      max_uses     = ?,
      active       = COALESCE(?, active),
      expires_at   = ?
    WHERE id = ?
  `).run(
    discount_pct !== undefined ? parseInt(discount_pct) : null,
    max_uses !== undefined ? (max_uses ? parseInt(max_uses) : null) : existing.max_uses,
    active !== undefined ? (active ? 1 : 0) : null,
    expires_at !== undefined ? expires_at : existing.expires_at,
    req.params.id,
  );

  res.json({ coupon: db.prepare('SELECT * FROM coupons WHERE id = ?').get(req.params.id) });
});

// ── DELETE /coupons/:id (admin) ────────────────
router.delete('/:id', requireAdmin, (req, res) => {
  const db = getDB();
  const r  = db.prepare('DELETE FROM coupons WHERE id = ?').run(req.params.id);
  if (!r.changes) return res.status(404).json({ error: 'Cupón no encontrado' });
  res.json({ ok: true });
});

export default router;
