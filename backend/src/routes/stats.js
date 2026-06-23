import { Router } from 'express';
import { getDB } from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.use(requireAuth);

// ── GET /stats ────────────────────────────────────
router.get('/', (req, res) => {
  const db = getDB();

  const botsTotal  = db.prepare('SELECT COUNT(*) as n FROM bots WHERE user_id = ?').get(req.user.id).n;
  const botsOnline = db.prepare("SELECT COUNT(*) as n FROM bots WHERE user_id = ? AND status = 'online'").get(req.user.id).n;
  const credits    = db.prepare('SELECT credits FROM users WHERE id = ?').get(req.user.id).credits;
  const totalSpent = db.prepare("SELECT COALESCE(SUM(amount),0) as n FROM credit_transactions WHERE user_id = ? AND type = 'bot_charge'").get(req.user.id).n;
  const txCount    = db.prepare('SELECT COUNT(*) as n FROM credit_transactions WHERE user_id = ?').get(req.user.id).n;
  const verified   = db.prepare('SELECT COUNT(*) as n FROM habbo_accounts WHERE user_id = ?').get(req.user.id).n;

  res.json({
    bots:      { total: botsTotal, online: botsOnline },
    credits:   { balance: credits, totalSpent },
    transactions: txCount,
    verifiedHotels: verified,
  });
});

// ── GET /stats/activity ───────────────────────────
// Returns daily credit activity for the last N days
router.get('/activity', (req, res) => {
  const days = Math.min(parseInt(req.query.days) || 30, 90);
  const db   = getDB();

  const rows = db.prepare(`
    SELECT date(created_at) as day, SUM(ABS(amount)) as total
    FROM credit_transactions
    WHERE user_id = ? AND created_at >= date('now', ? || ' days')
    GROUP BY day ORDER BY day ASC
  `).all(req.user.id, `-${days}`);

  res.json({ days, activity: rows });
});

// ── GET /stats/bots ───────────────────────────────
router.get('/bots', (req, res) => {
  const db   = getDB();
  const bots = db.prepare(`
    SELECT id, name, hotel, status, uptime_pct, actions, created_at
    FROM bots WHERE user_id = ? ORDER BY created_at DESC
  `).all(req.user.id);
  res.json({ bots });
});

export default router;
