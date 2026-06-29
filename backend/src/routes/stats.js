import { Router } from 'express';
import { getDB } from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();

// ── GET /stats/online — público ──────────────────────
router.get('/online', (_req, res) => {
  const db = getDB();
  const { n } = db.prepare(`
    SELECT COUNT(*) as n FROM users
    WHERE last_seen_at > datetime('now', '-5 minutes')
    AND email_verified = 1 AND is_banned = 0
  `).get();
  res.json({ online: n });
});

router.use(requireAuth);

// ── GET /stats — resumen global de plataforma ────────
router.get('/', (req, res) => {
  const db = getDB();

  const totalUsers       = db.prepare("SELECT COUNT(*) as n FROM users WHERE is_banned=0").get().n;
  const completedOrders  = db.prepare("SELECT COUNT(*) as n FROM service_orders WHERE status='completed'").get().n;
  const pendingOrders    = db.prepare("SELECT COUNT(*) as n FROM service_orders WHERE status IN ('pending','active')").get().n;
  const totalCredits     = db.prepare("SELECT COALESCE(SUM(credits),0) as n FROM users").get().n;
  const activeBots       = db.prepare("SELECT COUNT(*) as n FROM bots WHERE status='online'").get().n;

  // Valoración media global
  const ratingRow  = db.prepare("SELECT ROUND(AVG(rating),1) as avg FROM reviews").get();
  const avgRating  = ratingRow?.avg || null;

  // Top productos
  const topProducts = db.prepare(`
    SELECT p.id, p.name, p.hotel,
           COUNT(o.id) as total_orders,
           COALESCE(SUM(o.credits_paid),0) as total_revenue
    FROM products p
    LEFT JOIN service_orders o ON o.product_id = p.id AND o.status = 'completed'
    GROUP BY p.id
    ORDER BY total_orders DESC
    LIMIT 10
  `).all();

  res.json({
    totalUsers, completedOrders, pendingOrders,
    totalCredits, activeBots, avgRating, topProducts,
  });
});

// ── GET /stats/activity — actividad global (pedidos por día) ──
router.get('/activity', (req, res) => {
  const days = Math.min(parseInt(req.query.days) || 30, 90);
  const db   = getDB();

  const rows = db.prepare(`
    SELECT date(created_at) as date, COUNT(*) as count
    FROM service_orders
    WHERE created_at >= date('now', ? || ' days')
    GROUP BY date ORDER BY date ASC
  `).all(`-${days}`);

  // Rellenar días vacíos
  const map  = {};
  rows.forEach(r => { map[r.date] = r.count; });
  const activity = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    activity.push({ date: key, count: map[key] || 0 });
  }

  res.json({ days, activity });
});

// ── GET /stats/bots — bots del usuario ───────────────
router.get('/bots', (req, res) => {
  const db   = getDB();
  const bots = db.prepare(`
    SELECT id, name, hotel, status, uptime_pct, actions, created_at
    FROM bots WHERE user_id = ? ORDER BY created_at DESC
  `).all(req.user.id);
  res.json({ bots });
});

// ── GET /stats/leaderboard ────────────────────────────
router.get('/leaderboard', (req, res) => {
  const { by = 'orders', hotel, limit = 20 } = req.query;
  const db = getDB();

  let sql, params = [];

  if (by === 'credits') {
    // Por créditos gastados (suma de pedidos completados)
    sql = `
      SELECT u.id, u.username, u.avatar_url,
             COALESCE(SUM(o.credits_paid),0) as credits_spent,
             COUNT(o.id) as total_orders
      FROM users u
      LEFT JOIN service_orders o ON o.user_id = u.id AND o.status = 'completed'
      WHERE u.is_banned = 0
    `;
    if (hotel) {
      sql += ` AND EXISTS (SELECT 1 FROM habbo_accounts ha WHERE ha.user_id = u.id AND ha.hotel = ?)`;
      params.push(hotel);
    }
    sql += ` GROUP BY u.id ORDER BY credits_spent DESC LIMIT ?`;
  } else {
    // Por número de pedidos
    sql = `
      SELECT u.id, u.username, u.avatar_url,
             COUNT(o.id) as total_orders,
             COALESCE(SUM(o.credits_paid),0) as credits_spent
      FROM users u
      LEFT JOIN service_orders o ON o.user_id = u.id AND o.status = 'completed'
      WHERE u.is_banned = 0
    `;
    if (hotel) {
      sql += ` AND EXISTS (SELECT 1 FROM habbo_accounts ha WHERE ha.user_id = u.id AND ha.hotel = ?)`;
      params.push(hotel);
    }
    sql += ` GROUP BY u.id ORDER BY total_orders DESC LIMIT ?`;
  }

  params.push(Math.min(parseInt(limit) || 20, 100));

  const leaderboard = db.prepare(sql).all(...params);
  res.json({ leaderboard, by, hotel: hotel || 'all' });
});

export default router;
