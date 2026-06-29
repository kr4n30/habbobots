// ───────────────────────────────────────────────
//  HabboBots — Admin Metrics
//  GET /admin/metrics?period=7d|30d|90d
// ───────────────────────────────────────────────
import { Router }       from 'express';
import { getDB }        from '../database/init.js';
import { requireAdmin } from '../middleware/auth.js';

const router = Router();

router.get('/', requireAdmin, (req, res) => {
  const db     = getDB();
  const period = req.query.period || '30d';
  const days   = period === '7d' ? 7 : period === '90d' ? 90 : 30;

  // ── Ingresos por día (créditos vendidos) ─────────────────────
  const revenueByDay = db.prepare(`
    SELECT date(created_at) as day, SUM(credits) as credits, COUNT(*) as payments
    FROM payments
    WHERE status='completed'
      AND created_at >= datetime('now', '-${days} days')
    GROUP BY day ORDER BY day ASC
  `).all();

  // ── Bots rentados por día ─────────────────────────────────────
  const botsByDay = db.prepare(`
    SELECT date(created_at) as day, COUNT(*) as count
    FROM bots
    WHERE created_at >= datetime('now', '-${days} days')
    GROUP BY day ORDER BY day ASC
  `).all();

  // ── Pedidos de servicio por día ───────────────────────────────
  const ordersByDay = db.prepare(`
    SELECT date(created_at) as day, COUNT(*) as count, SUM(credits_paid) as credits
    FROM service_orders
    WHERE created_at >= datetime('now', '-${days} days')
    GROUP BY day ORDER BY day ASC
  `).all();

  // ── Nuevos usuarios por día ───────────────────────────────────
  const usersByDay = db.prepare(`
    SELECT date(created_at) as day, COUNT(*) as count
    FROM users
    WHERE created_at >= datetime('now', '-${days} days')
    GROUP BY day ORDER BY day ASC
  `).all();

  // ── KPIs globales ─────────────────────────────────────────────
  const totalUsers    = db.prepare('SELECT COUNT(*) as n FROM users').get().n;
  const activeUsers   = db.prepare(
    "SELECT COUNT(*) as n FROM users WHERE last_seen_at >= datetime('now', '-7 days')"
  ).get().n;
  const totalRevenue  = db.prepare(
    "SELECT COALESCE(SUM(credits),0) as n FROM payments WHERE status='completed'"
  ).get().n;
  const revenueMonth  = db.prepare(
    "SELECT COALESCE(SUM(credits),0) as n FROM payments WHERE status='completed' AND created_at >= datetime('now','-30 days')"
  ).get().n;
  const activeBots    = db.prepare("SELECT COUNT(*) as n FROM bots WHERE status='online'").get().n;
  const totalBots     = db.prepare('SELECT COUNT(*) as n FROM bots').get().n;
  const expiredBots   = db.prepare(
    "SELECT COUNT(*) as n FROM bots WHERE expires_at < datetime('now')"
  ).get().n;
  const openTickets   = db.prepare("SELECT COUNT(*) as n FROM tickets WHERE status='open'").get().n;

  // ── Top usuarios por créditos gastados ────────────────────────
  const topUsers = db.prepare(`
    SELECT u.username, us.total_credits_spent, us.total_services
    FROM user_stats us
    JOIN users u ON u.id = us.user_id
    ORDER BY us.total_credits_spent DESC LIMIT 10
  `).all();

  // ── Distribución de métodos de pago ──────────────────────────
  const paymentMethods = db.prepare(`
    SELECT method, COUNT(*) as count, SUM(credits) as credits
    FROM payments WHERE status='completed'
    GROUP BY method
  `).all();

  // ── Servicios más populares ───────────────────────────────────
  const topServices = db.prepare(`
    SELECT p.name, COUNT(*) as orders, SUM(so.credits_paid) as revenue
    FROM service_orders so
    JOIN products p ON p.id = so.product_id
    GROUP BY so.product_id ORDER BY orders DESC LIMIT 8
  `).all();

  // ── Churn (bots expirados no renovados últimos 30d) ──────────
  const churnRate = totalBots > 0 ? ((expiredBots / totalBots) * 100).toFixed(1) : '0.0';

  res.json({
    period,
    kpis: {
      totalUsers, activeUsers, totalRevenue, revenueMonth,
      activeBots, totalBots, expiredBots, openTickets, churnRate,
    },
    charts: { revenueByDay, botsByDay, ordersByDay, usersByDay },
    topUsers,
    paymentMethods,
    topServices,
  });
});

export default router;
