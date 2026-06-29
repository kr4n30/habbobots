/**
 * credits.js — Gestión de créditos y pagos
 *
 * Métodos de pago soportados:
 *   - paypal      → PayPal REST API v2 (Checkout)
 *   - nowpayments → NOWPayments (crypto: BTC, ETH, USDT…)
 *   - stripe      → Stripe (stub — descomentar para activar)
 *   - ingame      → Pago dentro de Habbo por el bot
 *
 * Variables de entorno necesarias:
 *   PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_MODE (sandbox|live)
 *   NOWPAYMENTS_API_KEY, NOWPAYMENTS_IPN_SECRET
 *   FRONTEND_URL, BACKEND_URL
 */

import express, { Router } from 'express';
import crypto from 'crypto';
import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';
import { addCredits } from '../services/credits.js';
import { discordPayment } from '../services/discord.js';

const router = Router();

// ── Packs de créditos ─────────────────────────────────────────────────────────
export const PACKS = {
  starter: { credits: 500,  price: 4.99,  name: 'Starter' },
  pro:     { credits: 1200, price: 9.99,  name: 'Pro',   bonus: 200 },
  elite:   { credits: 3500, price: 24.99, name: 'Elite', bonus: 500 },
};

// ── PayPal helpers ────────────────────────────────────────────────────────────
function paypalBase() {
  return (process.env.PAYPAL_MODE || 'sandbox') === 'live'
    ? 'https://api-m.paypal.com'
    : 'https://api-m.sandbox.paypal.com';
}

async function paypalToken() {
  const cid = process.env.PAYPAL_CLIENT_ID;
  const sec = process.env.PAYPAL_CLIENT_SECRET;
  if (!cid || !sec) throw new Error('PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET no configurados en .env');
  const res = await fetch(`${paypalBase()}/v1/oauth2/token`, {
    method: 'POST',
    headers: {
      Authorization: `Basic ${Buffer.from(`${cid}:${sec}`).toString('base64')}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: 'grant_type=client_credentials',
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`PayPal auth error ${res.status}: ${await res.text()}`);
  const { access_token } = await res.json();
  return access_token;
}

async function paypalReq(method, path, body, token) {
  const res = await fetch(`${paypalBase()}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}),
    signal: AbortSignal.timeout(15_000),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || `PayPal error ${res.status}`);
  return data;
}

// ── NOWPayments helpers ───────────────────────────────────────────────────────
function nowHeaders() {
  const key = process.env.NOWPAYMENTS_API_KEY;
  if (!key) throw new Error('NOWPAYMENTS_API_KEY no configurado en .env');
  return { 'x-api-key': key, 'Content-Type': 'application/json' };
}

async function nowReq(method, path, body) {
  const res = await fetch(`https://api.nowpayments.io/v1${path}`, {
    method,
    headers: nowHeaders(),
    ...(body ? { body: JSON.stringify(body) } : {}),
    signal: AbortSignal.timeout(15_000),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || `NOWPayments error ${res.status}`);
  return data;
}

// ── GET /credits/balance ──────────────────────────────────────────────────────
router.get('/balance', requireAuth, (req, res) => {
  const db   = getDB();
  const user = db.prepare('SELECT credits FROM users WHERE id = ?').get(req.user.id);
  res.json({ credits: user.credits });
});

// ── GET /credits/history ──────────────────────────────────────────────────────
router.get('/history', requireAuth, (req, res) => {
  const db  = getDB();
  const txs = db.prepare(
    'SELECT * FROM credit_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 50'
  ).all(req.user.id);
  res.json({ transactions: txs });
});

// ── GET /credits/packs ────────────────────────────────────────────────────────
router.get('/packs', (_req, res) => res.json({ packs: PACKS }));

// ── GET /credits/payments ─────────────────────────────────────────────────────
router.get('/payments', requireAuth, (req, res) => {
  const db = getDB();
  const payments = db.prepare(
    'SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 20'
  ).all(req.user.id);
  res.json({ payments });
});

// ── GET /credits/payments/:id ─────────────────────────────────────────────────
router.get('/payments/:id', requireAuth, (req, res) => {
  const db = getDB();
  const payment = db.prepare(
    'SELECT * FROM payments WHERE id = ? AND user_id = ?'
  ).get(req.params.id, req.user.id);
  if (!payment) return res.status(404).json({ error: 'Pago no encontrado' });
  res.json({ payment });
});

// ── POST /credits/checkout ────────────────────────────────────────────────────
router.post('/checkout', requireAuth, async (req, res, next) => {
  try {
    const { packId, method, currency = 'btc', couponCode } = req.body;
    const pack = PACKS[packId];
    if (!pack) return res.status(400).json({ error: 'Pack inválido' });

    // Aplicar cupón si se proporcionó
    const db = getDB();
    let discountPct = 0;
    let couponId    = null;
    if (couponCode) {
      const coupon = db.prepare(`
        SELECT * FROM coupons
        WHERE UPPER(code) = UPPER(?)
        AND active = 1
        AND (max_uses IS NULL OR uses < max_uses)
        AND (expires_at IS NULL OR expires_at > datetime('now'))
      `).get(couponCode.trim());
      if (!coupon) return res.status(400).json({ error: 'Cupón inválido o expirado' });
      discountPct = coupon.discount_pct;
      couponId    = coupon.id;
    }

    const finalPrice = +(pack.price * (1 - discountPct / 100)).toFixed(2);

    const paymentId = uuid();
    const frontUrl  = process.env.FRONTEND_URL || 'http://localhost:4321';

    // Incrementar uso del cupón si se aplicó
    if (couponId) {
      db.prepare('UPDATE coupons SET uses = uses + 1 WHERE id = ?').run(couponId);
    }

    // ── PayPal ────────────────────────────────────────────────────────────────
    if (method === 'paypal') {
      const token = await paypalToken();
      const descSuffix = discountPct > 0 ? ` (-${discountPct}%)` : '';
      const order = await paypalReq('POST', '/v2/checkout/orders', {
        intent: 'CAPTURE',
        purchase_units: [{
          amount:      { currency_code: 'EUR', value: finalPrice.toFixed(2) },
          description: `HabboBots — Pack ${pack.name} (${pack.credits} créditos)${descSuffix}`,
          custom_id:   paymentId,
        }],
        application_context: {
          brand_name:  'HabboBots',
          user_action: 'PAY_NOW',
          return_url:  `${frontUrl}/tienda/paypal-return?paymentId=${paymentId}`,
          cancel_url:  `${frontUrl}/tienda?cancelled=1`,
        },
      }, token);

      const approvalUrl = order.links?.find(l => l.rel === 'approve')?.href;
      if (!approvalUrl) throw new Error('PayPal no devolvió URL de aprobación');

      db.prepare(`
        INSERT INTO payments (id, user_id, pack_id, method, amount_eur, credits, status, external_id)
        VALUES (?, ?, ?, 'paypal', ?, ?, 'pending', ?)
      `).run(paymentId, req.user.id, packId, finalPrice, pack.credits, order.id);

      return res.json({ paymentId, approvalUrl, paypalOrderId: order.id, discountPct, finalPrice });
    }

    // ── NOWPayments (crypto) ──────────────────────────────────────────────────
    if (method === 'nowpayments') {
      const backUrl = process.env.BACKEND_URL || 'http://localhost:3001';
      const ipnUrl  = `${backUrl}/credits/webhook/nowpayments`;

      const payment = await nowReq('POST', '/payment', {
        price_amount:      finalPrice,
        price_currency:    'eur',
        pay_currency:      currency.toLowerCase(),
        order_id:          paymentId,
        order_description: `Pack ${pack.name} — ${pack.credits} créditos${discountPct > 0 ? ` (-${discountPct}%)` : ''}`,
        ipn_callback_url:  ipnUrl,
        success_url:       `${frontUrl}/tienda?crypto_success=1`,
        cancel_url:        `${frontUrl}/tienda?cancelled=1`,
      });

      db.prepare(`
        INSERT INTO payments
          (id, user_id, pack_id, method, amount_eur, credits, status, external_id, pay_address, pay_amount, pay_currency)
        VALUES (?, ?, ?, 'nowpayments', ?, ?, 'pending', ?, ?, ?, ?)
      `).run(
        paymentId, req.user.id, packId, finalPrice, pack.credits,
        String(payment.payment_id),
        payment.pay_address,
        payment.pay_amount,
        payment.pay_currency,
      );

      return res.json({
        paymentId,
        paymentNowId: payment.payment_id,
        payAddress:   payment.pay_address,
        payAmount:    payment.pay_amount,
        payCurrency:  payment.pay_currency,
        invoiceUrl:   payment.invoice_url || null,
        discountPct,
        finalPrice,
      });
    }

    // ── Stripe (stub) ─────────────────────────────────────────────────────────
    if (method === 'stripe') {
      return res.json({
        stub: true,
        message: 'Stripe no configurado. Añade STRIPE_SECRET_KEY en .env para activarlo.',
      });
    }

    res.status(400).json({ error: 'Método no soportado. Usa: paypal | nowpayments | stripe' });
  } catch (err) { next(err); }
});

// ── GET /credits/paypal/capture ───────────────────────────────────────────────
router.get('/paypal/capture', requireAuth, async (req, res, next) => {
  try {
    const { paymentId } = req.query;
    if (!paymentId) return res.status(400).json({ error: 'paymentId requerido' });

    const db      = getDB();
    const payment = db.prepare(
      "SELECT * FROM payments WHERE id = ? AND user_id = ? AND method = 'paypal'"
    ).get(paymentId, req.user.id);

    if (!payment) return res.status(404).json({ error: 'Pago no encontrado' });
    if (payment.status === 'completed')
      return res.json({ alreadyDone: true, credits: payment.credits });

    const accessTok = await paypalToken();
    const capture   = await paypalReq(
      'POST', `/v2/checkout/orders/${payment.external_id}/capture`, {}, accessTok
    );

    if (capture.status !== 'COMPLETED') {
      db.prepare("UPDATE payments SET status='failed' WHERE id=?").run(paymentId);
      return res.status(402).json({ error: `PayPal status: ${capture.status}` });
    }

    const pack = PACKS[payment.pack_id] || { name: payment.pack_id };
    addCredits(
      payment.user_id, payment.credits,
      `Compra PayPal: Pack ${pack.name}`, 'purchase', 'paypal', payment.external_id,
    );
    db.prepare("UPDATE payments SET status='completed', completed_at=datetime('now') WHERE id=?")
      .run(paymentId);

    discordPayment({ method: 'paypal', pack: pack.name, credits: payment.credits, userId: payment.user_id, amount: payment.amount_eur }).catch(() => {});
    res.json({ ok: true, credits: payment.credits, pack: pack.name });
  } catch (err) { next(err); }
});

// ── POST /credits/webhook/nowpayments ─────────────────────────────────────────
router.post('/webhook/nowpayments', express.json(), async (req, res, next) => {
  try {
    const secret = process.env.NOWPAYMENTS_IPN_SECRET;
    if (secret) {
      const sig      = req.headers['x-nowpayments-sig'];
      const expected = crypto.createHmac('sha512', secret)
        .update(JSON.stringify(sortDeep(req.body))).digest('hex');
      if (sig !== expected) {
        console.warn('[NOWPayments] Firma IPN inválida');
        return res.status(401).json({ error: 'Firma inválida' });
      }
    }

    const { payment_id, payment_status, order_id } = req.body;
    const db      = getDB();
    const payment = db.prepare(
      "SELECT * FROM payments WHERE id = ? AND method = 'nowpayments'"
    ).get(order_id);

    if (!payment) return res.json({ ok: true });

    db.prepare("UPDATE payments SET external_id=?, status=? WHERE id=?")
      .run(String(payment_id), payment_status, order_id);

    const done = ['finished', 'confirmed', 'partially_paid'];
    if (done.includes(payment_status) && payment.status !== 'completed') {
      const pack = PACKS[payment.pack_id] || { name: payment.pack_id };
      addCredits(
        payment.user_id, payment.credits,
        `Compra crypto (${req.body.pay_currency || '?'}): Pack ${pack.name}`,
        'purchase', 'nowpayments', String(payment_id),
      );
      db.prepare("UPDATE payments SET status='completed', completed_at=datetime('now') WHERE id=?")
        .run(order_id);
      discordPayment({ method: 'nowpayments', pack: pack.name, credits: payment.credits, userId: payment.user_id, amount: payment.amount_eur }).catch(() => {});
      console.log(`[NOWPayments] +${payment.credits} cr → user ${payment.user_id}`);
    }
    res.json({ ok: true });
  } catch (err) { next(err); }
});

// ── POST /credits/webhook/stripe ──────────────────────────────────────────────
router.post('/webhook/stripe', express.raw({ type: 'application/json' }), async (req, res, next) => {
  try {
    // Descomentar para Stripe:
    // const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);
    // const event  = stripe.webhooks.constructEvent(req.body, req.headers['stripe-signature'], process.env.STRIPE_WEBHOOK_SECRET);
    // if (event.type === 'payment_intent.succeeded') { ... addCredits(...) }
    res.json({ received: true });
  } catch (err) { next(err); }
});

// ── POST /credits/ingame ──────────────────────────────────────────────────────
router.post('/ingame', (req, res, next) => {
  try {
    const { packId, habboName, hotel, apiKey } = req.body;
    if (!apiKey || apiKey !== process.env.BOT_VPS_API_KEY)
      return res.status(403).json({ error: 'API key inválida' });
    const pack = PACKS[packId];
    if (!pack) return res.status(400).json({ error: 'Pack inválido' });
    const db      = getDB();
    const account = db.prepare(
      'SELECT user_id FROM habbo_accounts WHERE habbo_name = ? AND hotel = ?'
    ).get(habboName, hotel);
    if (!account) return res.status(404).json({ error: 'Cuenta Habbo no vinculada' });
    const newBalance = addCredits(
      account.user_id, pack.credits,
      `Pago in-game: ${pack.name} (${habboName} @ habbo.${hotel})`, 'ingame',
    );
    res.json({ message: `${pack.credits} créditos añadidos`, newBalance });
  } catch (err) { next(err); }
});

// ── Util ──────────────────────────────────────────────────────────────────────
function sortDeep(obj) {
  if (Array.isArray(obj)) return obj.map(sortDeep);
  if (obj && typeof obj === 'object')
    return Object.fromEntries(Object.keys(obj).sort().map(k => [k, sortDeep(obj[k])]));
  return obj;
}

export default router;
