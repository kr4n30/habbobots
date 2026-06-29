import { Router } from 'express';
import { v4 as uuid } from 'uuid';
import { getDB }       from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';
import { addCredits }  from '../services/credits.js';
import { notify }      from '../services/socket.js';

const router = Router();

// Créditos por referido (al registrarse y al hacer primer pedido)
const CREDITS_REFERRER       = 100; // quien refiere
const CREDITS_REFERRED       = 50;  // quien usa el código

// ── GET /affiliates/my ────────────────────────────
router.get('/my', requireAuth, (req, res) => {
  const db = getDB();
  const user = db.prepare('SELECT id, referral_code FROM users WHERE id=?').get(req.user.id);

  // Generar código si no tiene
  if (!user.referral_code) {
    const code = `HB-${req.user.id.slice(0,6).toUpperCase()}`;
    db.prepare('UPDATE users SET referral_code=? WHERE id=?').run(code, req.user.id);
    user.referral_code = code;
  }

  // Estadísticas de referidos
  const referred = db.prepare(`
    SELECT u.id, u.username, u.created_at,
           EXISTS(SELECT 1 FROM affiliate_rewards ar WHERE ar.referred_id=u.id) as rewarded
    FROM users u WHERE u.referred_by=?
    ORDER BY u.created_at DESC
  `).all(req.user.id);

  const totalRewards = db.prepare(
    `SELECT COALESCE(SUM(credits_given),0) as n FROM affiliate_rewards WHERE referrer_id=?`
  ).get(req.user.id).n;

  res.json({
    code:   user.referral_code,
    url:    `${process.env.FRONTEND_URL || ''}/?ref=${user.referral_code}`,
    referred,
    totalReferrals: referred.length,
    totalRewards,
    pendingRewards: referred.filter(r => !r.rewarded).length,
  });
});

// ── GET /affiliates/validate/:code — Público ─────
router.get('/validate/:code', (req, res) => {
  const db   = getDB();
  const user = db.prepare(`
    SELECT id, username FROM users WHERE referral_code=?
  `).get(req.params.code);
  if (!user) return res.status(404).json({ error: 'Código inválido' });
  res.json({ valid: true, referrer: user.username });
});

// ── POST /affiliates/mark-reward ─────────────────
// Llamado internamente cuando un referido hace su primer pedido
router.post('/mark-reward', requireAuth, (req, res) => {
  const db = getDB();

  // Comprobar si el usuario fue referido
  const referredUser = db.prepare('SELECT id, referred_by FROM users WHERE id=?').get(req.user.id);
  if (!referredUser?.referred_by)
    return res.json({ rewarded: false, message: 'No fue referido' });

  // Comprobar si ya se dio el reward
  const alreadyRewarded = db.prepare(
    'SELECT id FROM affiliate_rewards WHERE referred_id=? AND referred_id IS NOT NULL'
  ).get(req.user.id);
  if (alreadyRewarded)
    return res.json({ rewarded: false, message: 'Ya recompensado' });

  // Comprobar que el referidor existe
  const referrer = db.prepare('SELECT id, username FROM users WHERE id=?').get(referredUser.referred_by);
  if (!referrer) return res.json({ rewarded: false });

  // Comprobar que el referido tiene al menos un pedido completado
  const hasOrder = db.prepare(
    `SELECT id FROM service_orders WHERE user_id=? AND status='completed' LIMIT 1`
  ).get(req.user.id);
  if (!hasOrder) return res.json({ rewarded: false, message: 'Sin pedidos completados' });

  // Dar créditos
  const rewardId = uuid();
  db.transaction(() => {
    addCredits(referredUser.referred_by, CREDITS_REFERRER,
      `Referido: ${req.user.username || req.user.email}`, 'bonus');
    addCredits(req.user.id, CREDITS_REFERRED,
      `Bono bienvenida por código de referido`, 'bonus');

    db.prepare(`INSERT INTO affiliate_rewards (id,referrer_id,referred_id,credits_given,reason) VALUES (?,?,?,?,?)`)
      .run(rewardId, referredUser.referred_by, req.user.id,
           CREDITS_REFERRER + CREDITS_REFERRED, 'first_order');
  })();

  notify(referredUser.referred_by, {
    type: 'success',
    title: `¡Referido activo! +${CREDITS_REFERRER} créditos`,
    message: `${req.user.username || 'Tu referido'} hizo su primer pedido.`,
  });
  notify(req.user.id, {
    type: 'success',
    title: `+${CREDITS_REFERRED} créditos — bono bienvenida`,
    message: 'Gracias por unirte con un código de referido.',
  });

  res.json({ rewarded: true, creditsGiven: CREDITS_REFERRER });
});

export default router;
