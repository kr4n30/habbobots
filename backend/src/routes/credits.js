import express, { Router } from 'express';
import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';
import { addCredits } from '../services/credits.js'; // ← importado desde el servicio, sin duplicado

const router = Router();
router.use(requireAuth);

const PACKS = {
  starter: { credits: 500,  price: 4.99,  name: 'Starter' },
  pro:     { credits: 1200, price: 9.99,  name: 'Pro',   bonus: 200 },
  elite:   { credits: 3500, price: 24.99, name: 'Elite', bonus: 500 },
};

// ── GET /credits/balance ──────────────────────────
router.get('/balance', (req, res) => {
  const db   = getDB();
  const user = db.prepare('SELECT credits FROM users WHERE id = ?').get(req.user.id);
  res.json({ credits: user.credits });
});

// ── GET /credits/history ──────────────────────────
router.get('/history', (req, res) => {
  const db  = getDB();
  const txs = db.prepare(`
    SELECT * FROM credit_transactions WHERE user_id = ?
    ORDER BY created_at DESC LIMIT 50
  `).all(req.user.id);
  res.json({ transactions: txs });
});

// ── GET /credits/packs ────────────────────────────
router.get('/packs', (_req, res) => {
  res.json({ packs: PACKS });
});

// ── POST /credits/checkout ────────────────────────
router.post('/checkout', async (req, res, next) => {
  try {
    const { packId, method } = req.body;
    const pack = PACKS[packId];
    if (!pack) return res.status(400).json({ error: 'Pack inválido' });

    if (method === 'stripe') {
      // Producción: descomenta y añade el SDK de Stripe
      // import Stripe from 'stripe';
      // const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);
      // const intent = await stripe.paymentIntents.create({
      //   amount: Math.round(pack.price * 100),
      //   currency: 'eur',
      //   metadata: { userId: req.user.id, packId },
      // });
      // return res.json({ clientSecret: intent.client_secret });

      // Dev stub — simulamos un clientSecret:
      return res.json({
        clientSecret: `stub_pi_${uuid()}`,
        pack,
        stub: true,
        message: 'Configura STRIPE_SECRET_KEY para pagos reales',
      });
    }

    if (method === 'paypal') {
      return res.json({ message: 'PayPal próximamente', pack });
    }

    res.status(400).json({ error: 'Método no soportado. Usa: stripe | paypal' });
  } catch (err) { next(err); }
});

// ── POST /credits/webhook/stripe ──────────────────
// Stripe llama a este endpoint tras un pago exitoso.
// Debe estar excluido del middleware JSON normal (usa raw body).
router.post(
  '/webhook/stripe',
  express.raw({ type: 'application/json' }),
  async (req, res, next) => {
    try {
      const sig = req.headers['stripe-signature'];
      if (!sig) return res.status(400).json({ error: 'Firma Stripe requerida' });

      // Producción:
      // const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);
      // const event  = stripe.webhooks.constructEvent(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET);
      // if (event.type === 'payment_intent.succeeded') {
      //   const intent  = event.data.object;
      //   const { userId, packId } = intent.metadata;
      //   const pack = PACKS[packId];
      //   if (pack && userId) {
      //     addCredits(userId, pack.credits, `Compra ${pack.name}`, 'stripe', intent.id);
      //   }
      // }

      res.json({ received: true });
    } catch (err) { next(err); }
  }
);

// ── POST /credits/ingame ──────────────────────────
// El bot en la sala de Habbo llama aquí tras confirmar el pago.
router.post('/ingame', async (req, res, next) => {
  try {
    const { packId, habboName, hotel, apiKey } = req.body;

    if (!apiKey || apiKey !== process.env.BOT_VPS_API_KEY) {
      return res.status(403).json({ error: 'API key inválida' });
    }

    const pack = PACKS[packId];
    if (!pack) return res.status(400).json({ error: 'Pack inválido' });

    const db      = getDB();
    const account = db.prepare(
      'SELECT user_id FROM habbo_accounts WHERE habbo_name = ? AND hotel = ?'
    ).get(habboName, hotel);

    if (!account) {
      return res.status(404).json({ error: 'Cuenta Habbo no vinculada a ningún usuario' });
    }

    const newBalance = addCredits(
      account.user_id,
      pack.credits,
      `Pago in-game: ${pack.name} (${habboName} @ habbo.${hotel})`,
      'ingame',
    );

    res.json({ message: `${pack.credits} créditos añadidos`, newBalance });
  } catch (err) { next(err); }
});

export default router;
