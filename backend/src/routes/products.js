import { Router } from 'express';
import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';
import { chargeCredits, addCredits } from '../services/credits.js';
import { discordOrder } from '../services/discord.js';

const router = Router();

// ── GET /products ─────────────────────────────────
// Público (sin auth) — lista productos activos
router.get('/', (req, res) => {
  const db = getDB();
  const { hotel } = req.query;

  let sql = `SELECT * FROM products WHERE active = 1`;
  const params = [];

  if (hotel) {
    sql += ` AND (hotel IS NULL OR hotel = ?)`;
    params.push(hotel);
  }

  sql += ` ORDER BY sort_order ASC, price ASC`;
  const products = db.prepare(sql).all(...params);
  res.json({ products });
});

// ── GET /products/orders/my ───────────────────────
// Historial de pedidos del usuario (ANTES de /:id para evitar conflicto de ruta)
router.get('/orders/my', requireAuth, (req, res) => {
  const db     = getDB();
  const orders = db.prepare(`
    SELECT so.*, p.name as product_name, p.type as product_type, p.description as product_description
    FROM service_orders so
    JOIN products p ON p.id = so.product_id
    WHERE so.user_id = ?
    ORDER BY so.created_at DESC
    LIMIT 50
  `).all(req.user.id);
  res.json({ orders });
});

// ── POST /products/orders/:id/cancel ─────────────
router.post('/orders/:id/cancel', requireAuth, (req, res, next) => {
  try {
    const db    = getDB();
    const order = db.prepare(
      "SELECT * FROM service_orders WHERE id = ? AND user_id = ?"
    ).get(req.params.id, req.user.id);

    if (!order) return res.status(404).json({ error: 'Pedido no encontrado' });
    if (!['pending'].includes(order.status))
      return res.status(400).json({ error: 'Solo se pueden cancelar pedidos pendientes' });

    db.prepare("UPDATE service_orders SET status='cancelled', updated_at=datetime('now') WHERE id=?")
      .run(order.id);

    // Reembolsar créditos
    if (order.credits_paid > 0) {
      try { addCredits(order.user_id, order.credits_paid, `Cancelación pedido ${order.id}`, 'refund'); } catch {}
    }

    res.json({ ok: true, message: 'Pedido cancelado y créditos reembolsados' });
  } catch (err) { next(err); }
});

// ── GET /products/:id ─────────────────────────────
router.get('/:id', (req, res) => {
  const db      = getDB();
  const product = db.prepare('SELECT * FROM products WHERE id = ? AND active = 1').get(req.params.id);
  if (!product) return res.status(404).json({ error: 'Producto no encontrado' });
  res.json({ product });
});

// ── POST /products/:id/order ──────────────────────
// Comprar un servicio con créditos
router.post('/:id/order', requireAuth, (req, res, next) => {
  try {
    const { hotel, habboName, notes, bot_count, duration, room_id } = req.body;
    if (!hotel || !habboName)
      return res.status(400).json({ error: 'hotel y habboName son obligatorios' });

    const db      = getDB();
    const product = db.prepare('SELECT * FROM products WHERE id = ? AND active = 1').get(req.params.id);
    if (!product) return res.status(404).json({ error: 'Producto no encontrado' });

    // Verificar hotel compatible
    if (product.hotel && product.hotel !== hotel)
      return res.status(400).json({ error: `Este servicio solo está disponible en habbo.${product.hotel}` });

    // Verificar que el habboName pertenece al usuario
    const habboAccount = db.prepare(
      'SELECT * FROM habbo_accounts WHERE user_id = ? AND hotel = ? AND habbo_name = ?'
    ).get(req.user.id, hotel, habboName);
    if (!habboAccount)
      return res.status(400).json({ error: 'Ese personaje no está vinculado a tu cuenta en ese hotel' });

    // Verificar límite de compras si aplica
    if (product.max_quantity) {
      const bought = db.prepare(
        `SELECT COUNT(*) as n FROM service_orders WHERE user_id = ? AND product_id = ? AND status != 'cancelled'`
      ).get(req.user.id, product.id).n;
      if (bought >= product.max_quantity)
        return res.status(400).json({ error: `Solo puedes comprar este servicio ${product.max_quantity} vez/veces` });
    }

    // Precio dinámico para room_fill y raid (bots × horas × price_per_bot_hour)
    let actualPrice    = product.price;
    let actualDuration = product.duration;
    let actualBotCount = bot_count ? parseInt(bot_count) : null;
    let orderNotes     = notes || null;

    if (['room_fill', 'raid'].includes(product.type) && bot_count && duration) {
      const hours = Math.ceil(parseInt(duration) / 3600);
      const bots  = parseInt(bot_count);
      if (isNaN(hours) || isNaN(bots) || hours < 1 || bots < 1)
        return res.status(400).json({ error: 'Duración y cantidad de bots inválidas' });
      actualPrice    = bots * hours * product.price;
      actualDuration = parseInt(duration);
      actualBotCount = bots;
      orderNotes = `${bots} bots × ${hours}h` + (notes ? ` · ${notes}` : '');
    }

    // Cobrar créditos
    const user = db.prepare('SELECT credits FROM users WHERE id = ?').get(req.user.id);
    if (user.credits < actualPrice)
      return res.status(402).json({ error: `Créditos insuficientes. Necesitas ${actualPrice}, tienes ${user.credits}.` });

    const orderId = uuid();

    // Calcular ends_at si el servicio tiene duración
    let endsAt = null;
    if (actualDuration) {
      endsAt = new Date(Date.now() + actualDuration * 1000).toISOString();
    }

    db.transaction(() => {
      chargeCredits(
        req.user.id,
        actualPrice,
        `Servicio: ${product.name} → ${habboName}@habbo.${hotel}`,
        'service',
        orderId
      );

      db.prepare(`
        INSERT INTO service_orders (id, user_id, product_id, hotel, habbo_name, credits_paid, notes, ends_at, room_id, bot_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(orderId, req.user.id, product.id, hotel, habboName, actualPrice, orderNotes, endsAt,
             room_id || null, actualBotCount);

      // Actualizar stats
      db.prepare(`
        INSERT INTO user_stats (user_id, total_services, total_credits_spent)
        VALUES (?, 1, ?)
        ON CONFLICT(user_id) DO UPDATE SET
          total_services      = total_services + 1,
          total_credits_spent = total_credits_spent + ?,
          updated_at          = datetime('now')
      `).run(req.user.id, actualPrice, actualPrice);
    })();

    const order = db.prepare('SELECT * FROM service_orders WHERE id = ?').get(orderId);
    discordOrder(order, product).catch(() => {});
    res.status(201).json({ order, message: `Servicio "${product.name}" contratado correctamente` });
  } catch (err) { next(err); }
});

export default router;
