// ───────────────────────────────────────────────
//  HabboBots — Admin Routes
//  Requiere rol admin o moderator
// ───────────────────────────────────────────────

import { Router } from 'express';
import { v4 as uuid } from 'uuid';
import path from 'path';
import { fileURLToPath } from 'url';
import { getDB } from '../database/init.js';
import { requireAdmin } from '../middleware/auth.js';
import { addCredits }    from '../services/credits.js';
import { notify }        from '../services/socket.js';
import { sendVPSCommand } from '../services/vps.js';

// ── Multer para subida de imágenes de producto ────
let upload = null;
try {
  const multer = (await import('multer')).default;
  const __dirname = path.dirname(fileURLToPath(import.meta.url));
  const uploadDir = path.resolve(__dirname, '../../public/uploads/products');
  const { mkdirSync } = await import('fs');
  mkdirSync(uploadDir, { recursive: true });

  const storage = multer.diskStorage({
    destination: (_req, _file, cb) => cb(null, uploadDir),
    filename:    (_req, file, cb) => {
      const ext  = path.extname(file.originalname).toLowerCase() || '.jpg';
      const name = `prod_${Date.now()}${ext}`;
      cb(null, name);
    },
  });
  upload = multer({
    storage,
    limits: { fileSize: 4 * 1024 * 1024 }, // 4 MB
    fileFilter: (_req, file, cb) => {
      if (file.mimetype.startsWith('image/')) cb(null, true);
      else cb(new Error('Solo se permiten imágenes'));
    },
  });
} catch {
  console.warn('[admin] multer no instalado — sube imágenes desactivado. Ejecuta: npm install multer');
}

const router = Router();
router.use(requireAdmin);

// ── GET /admin/overview ───────────────────────────
router.get('/overview', (_req, res) => {
  const db = getDB();

  const totalUsers    = db.prepare("SELECT COUNT(*) as n FROM users WHERE email_verified=1").get().n;
  const newToday      = db.prepare("SELECT COUNT(*) as n FROM users WHERE date(created_at)=date('now')").get().n;
  const totalOrders   = db.prepare("SELECT COUNT(*) as n FROM service_orders").get().n;
  const pendingOrders = db.prepare("SELECT COUNT(*) as n FROM service_orders WHERE status='pending'").get().n;
  const activeOrders  = db.prepare("SELECT COUNT(*) as n FROM service_orders WHERE status='active'").get().n;
  const revenue       = db.prepare("SELECT COALESCE(SUM(credits_paid),0) as n FROM service_orders WHERE status!='cancelled'").get().n;
  const totalProducts = db.prepare("SELECT COUNT(*) as n FROM products WHERE active=1").get().n;
  const bannedUsers   = db.prepare("SELECT COUNT(*) as n FROM users WHERE is_banned=1").get().n;
  const onlineUsers   = db.prepare("SELECT COUNT(*) as n FROM users WHERE last_seen_at > datetime('now','-5 minutes') AND is_banned=0").get().n;
  const avgRating     = db.prepare("SELECT ROUND(AVG(rating),1) as n FROM reviews").get().n;

  // Últimas 7 órdenes
  const recentOrders = db.prepare(`
    SELECT so.id, so.status, so.credits_paid, so.created_at, so.habbo_name, so.hotel,
           p.name as product_name, u.username, u.email
    FROM service_orders so
    JOIN products p ON p.id=so.product_id
    JOIN users u    ON u.id=so.user_id
    ORDER BY so.created_at DESC LIMIT 7
  `).all();

  // Últimos 5 usuarios registrados
  const recentUsers = db.prepare(`
    SELECT id, username, email, role, credits, created_at, is_banned
    FROM users ORDER BY created_at DESC LIMIT 5
  `).all();

  res.json({
    users:    { total: totalUsers, newToday, banned: bannedUsers, online: onlineUsers },
    orders:   { total: totalOrders, pending: pendingOrders, active: activeOrders },
    revenue,
    products: { active: totalProducts },
    avgRating: avgRating || 0,
    recentOrders,
    recentUsers,
  });
});

// ── GET /admin/users ──────────────────────────────
router.get('/users', (req, res) => {
  const db = getDB();
  const { search = '', role, banned, page = 1, limit = 30 } = req.query;
  const offset = (parseInt(page) - 1) * parseInt(limit);

  let sql    = `SELECT u.*, GROUP_CONCAT(ha.hotel) as hotels
                FROM users u
                LEFT JOIN habbo_accounts ha ON ha.user_id = u.id
                WHERE 1=1`;
  const params = [];

  if (search) {
    sql += ` AND (u.username LIKE ? OR u.email LIKE ?)`;
    params.push(`%${search}%`, `%${search}%`);
  }
  if (role)   { sql += ` AND u.role=?`;     params.push(role); }
  if (banned !== undefined) { sql += ` AND u.is_banned=?`; params.push(banned === '1' ? 1 : 0); }

  sql += ` GROUP BY u.id ORDER BY u.created_at DESC LIMIT ? OFFSET ?`;
  params.push(parseInt(limit), offset);

  const users = db.prepare(sql).all(...params);
  const total = db.prepare(`SELECT COUNT(*) as n FROM users WHERE 1=1`).get().n;

  res.json({ users, total, page: parseInt(page), limit: parseInt(limit) });
});

// ── PATCH /admin/users/:id ────────────────────────
router.patch('/users/:id', (req, res) => {
  const db   = getDB();
  const user = db.prepare('SELECT * FROM users WHERE id=?').get(req.params.id);
  if (!user) return res.status(404).json({ error: 'Usuario no encontrado' });

  const { ban, ban_reason, unban, role, credits_adjust, credits_note } = req.body;

  // Ban / unban
  if (ban !== undefined) {
    if (ban) {
      db.prepare(`UPDATE users SET is_banned=1, ban_reason=?, ban_expires=? WHERE id=?`)
        .run(ban_reason || 'Baneo manual', req.body.ban_expires || null, req.params.id);
      // Insertar en tabla bans
      db.prepare(`INSERT INTO bans (id,user_id,reason,banned_by,active) VALUES (?,?,?,?,1)`)
        .run(uuid(), req.params.id, ban_reason || 'Baneo manual', req.user.id);
      // Notificar
      notify(req.params.id, { type: 'danger', title: 'Cuenta suspendida', message: ban_reason || 'Tu cuenta ha sido suspendida.' });
    } else {
      db.prepare(`UPDATE users SET is_banned=0, ban_reason=NULL, ban_expires=NULL WHERE id=?`)
        .run(req.params.id);
      db.prepare(`UPDATE bans SET active=0 WHERE user_id=? AND active=1`).run(req.params.id);
    }
  }

  // Cambiar rol
  if (role && ['user','moderator','admin'].includes(role)) {
    if (req.user.role !== 'admin') return res.status(403).json({ error: 'Solo admin puede cambiar roles' });
    db.prepare(`UPDATE users SET role=? WHERE id=?`).run(role, req.params.id);
  }

  // Ajustar créditos
  if (credits_adjust && parseInt(credits_adjust) !== 0) {
    const amount = parseInt(credits_adjust);
    addCredits(req.params.id, amount, credits_note || `Ajuste manual por admin`, 'admin_adjust');
    const newBalance = db.prepare('SELECT credits FROM users WHERE id=?').get(req.params.id).credits;
    notify(req.params.id, {
      type:    amount > 0 ? 'success' : 'warning',
      title:   amount > 0 ? `+${amount} créditos añadidos` : `${amount} créditos ajustados`,
      message: credits_note || 'Ajuste por administrador',
    });
  }

  // Log de auditoría
  db.prepare(`INSERT INTO audit_logs (id,user_id,action,target_id,details,ip) VALUES (?,?,?,?,?,?)`)
    .run(uuid(), req.user.id, 'admin_user_update', req.params.id,
      JSON.stringify({ ban, role, credits_adjust }), req.ip);

  const updated = db.prepare('SELECT * FROM users WHERE id=?').get(req.params.id);
  const { password: _, ...safe } = updated;
  res.json({ user: safe });
});

// ── GET /admin/orders ─────────────────────────────
router.get('/orders', (req, res) => {
  const db = getDB();
  const { status, hotel, search, page = 1, limit = 30 } = req.query;
  const offset = (parseInt(page) - 1) * parseInt(limit);

  let sql = `
    SELECT so.*, p.name as product_name, p.type as product_type,
           u.username, u.email
    FROM service_orders so
    JOIN products p ON p.id=so.product_id
    JOIN users u    ON u.id=so.user_id
    WHERE 1=1
  `;
  const params = [];

  if (status) { sql += ` AND so.status=?`;     params.push(status); }
  if (hotel)  { sql += ` AND so.hotel=?`;       params.push(hotel); }
  if (search) {
    sql += ` AND (u.username LIKE ? OR so.habbo_name LIKE ? OR p.name LIKE ?)`;
    params.push(`%${search}%`, `%${search}%`, `%${search}%`);
  }

  sql += ` ORDER BY so.created_at DESC LIMIT ? OFFSET ?`;
  params.push(parseInt(limit), offset);

  const orders = db.prepare(sql).all(...params);
  const total  = db.prepare(`SELECT COUNT(*) as n FROM service_orders WHERE 1=1`).get().n;

  res.json({ orders, total, page: parseInt(page) });
});

// ── PATCH /admin/orders/:id/status ───────────────
router.patch('/orders/:id/status', (req, res) => {
  const db    = getDB();
  const { status, notes } = req.body;
  const allowed = ['pending','active','completed','cancelled','failed'];
  if (!allowed.includes(status))
    return res.status(400).json({ error: 'Estado inválido' });

  const order = db.prepare(`
    SELECT so.*, p.name as product_name, u.username
    FROM service_orders so
    JOIN products p ON p.id=so.product_id
    JOIN users u    ON u.id=so.user_id
    WHERE so.id=?
  `).get(req.params.id);
  if (!order) return res.status(404).json({ error: 'Pedido no encontrado' });

  // Si se cancela, devolver créditos
  if (status === 'cancelled' && order.status !== 'cancelled') {
    addCredits(order.user_id, order.credits_paid, `Reembolso: ${order.product_name}`, 'refund');
    const newBal = db.prepare('SELECT credits FROM users WHERE id=?').get(order.user_id).credits;
    notify(order.user_id, {
      type: 'info', title: 'Pedido cancelado — reembolso',
      message: `Se han devuelto ${order.credits_paid} créditos a tu cuenta.`,
    });
  }

  const endsAt = status === 'active' && !order.ends_at
    ? null : order.ends_at;

  db.prepare(`
    UPDATE service_orders
    SET status=?, updated_at=datetime('now'), started_at = CASE WHEN ? = 'active' AND started_at IS NULL THEN datetime('now') ELSE started_at END
    WHERE id=?
  `).run(status, status, req.params.id);

  if (notes) {
    db.prepare(`UPDATE service_orders SET notes=? WHERE id=?`).run(notes, req.params.id);
  }

  const updatedOrder = db.prepare('SELECT * FROM service_orders WHERE id=?').get(req.params.id);
  notify(order.user_id, {
    type:    status === 'completed' ? 'success' : status === 'cancelled' ? 'warning' : 'info',
    title:   `Pedido ${status}`,
    message: `${order.product_name} → ${order.habbo_name}`,
    data:    { orderId: order.id, status },
  });

  // Audit
  db.prepare(`INSERT INTO audit_logs (id,user_id,action,target_id,details) VALUES (?,?,?,?,?)`)
    .run(uuid(), req.user.id, 'admin_order_update', req.params.id, JSON.stringify({ status, notes }));

  res.json({ order: updatedOrder });
});

// ── GET /admin/products ───────────────────────────
router.get('/products', (_req, res) => {
  const db = getDB();
  const products = db.prepare(`
    SELECT p.*, COUNT(so.id) as total_orders,
           COALESCE(SUM(so.credits_paid),0) as total_revenue
    FROM products p
    LEFT JOIN service_orders so ON so.product_id=p.id AND so.status != 'cancelled'
    GROUP BY p.id ORDER BY p.sort_order ASC, p.created_at ASC
  `).all();
  res.json({ products });
});

// ── POST /admin/products ──────────────────────────
router.post('/products', (req, res) => {
  const db = getDB();
  const { name, description, type, price, hotel, duration, max_quantity, sort_order = 99 } = req.body;
  if (!name || !type || price === undefined)
    return res.status(400).json({ error: 'name, type y price son obligatorios' });

  const id = `prod_${Date.now()}`;
  db.prepare(`
    INSERT INTO products (id,name,description,type,price,hotel,duration,max_quantity,active,sort_order)
    VALUES (?,?,?,?,?,?,?,?,1,?)
  `).run(id, name, description||null, type, parseInt(price), hotel||null,
         duration?parseInt(duration):null, max_quantity?parseInt(max_quantity):null, parseInt(sort_order));

  db.prepare(`INSERT INTO audit_logs (id,user_id,action,target_id,details) VALUES (?,?,?,?,?)`)
    .run(uuid(), req.user.id, 'admin_product_create', id, JSON.stringify({ name, type, price }));

  const product = db.prepare('SELECT * FROM products WHERE id=?').get(id);
  res.status(201).json({ product });
});

// ── PATCH /admin/products/:id ─────────────────────
router.patch('/products/:id', (req, res) => {
  const db = getDB();
  const { name, description, price, hotel, duration, max_quantity, active, sort_order, image_url } = req.body;

  const existing = db.prepare('SELECT * FROM products WHERE id=?').get(req.params.id);
  if (!existing) return res.status(404).json({ error: 'Producto no encontrado' });

  db.prepare(`
    UPDATE products SET
      name        = COALESCE(?, name),
      description = COALESCE(?, description),
      price       = COALESCE(?, price),
      hotel       = ?,
      duration    = ?,
      max_quantity= ?,
      active      = COALESCE(?, active),
      sort_order  = COALESCE(?, sort_order),
      image_url   = COALESCE(?, image_url)
    WHERE id=?
  `).run(
    name || null, description || null, price !== undefined ? parseInt(price) : null,
    hotel !== undefined ? hotel : existing.hotel,
    duration !== undefined ? (duration ? parseInt(duration) : null) : existing.duration,
    max_quantity !== undefined ? (max_quantity ? parseInt(max_quantity) : null) : existing.max_quantity,
    active !== undefined ? (active ? 1 : 0) : null,
    sort_order !== undefined ? parseInt(sort_order) : null,
    image_url || null,
    req.params.id,
  );

  db.prepare(`INSERT INTO audit_logs (id,user_id,action,target_id,details) VALUES (?,?,?,?,?)`)
    .run(uuid(), req.user.id, 'admin_product_update', req.params.id, JSON.stringify(req.body));

  const product = db.prepare('SELECT * FROM products WHERE id=?').get(req.params.id);
  res.json({ product });
});

// ── POST /admin/products/:id/upload-image ─────────
router.post('/products/:id/upload-image', (req, res, next) => {
  if (!upload) return res.status(503).json({ error: 'Módulo multer no disponible. Ejecuta npm install en el backend.' });

  upload.single('image')(req, res, async (err) => {
    if (err) return res.status(400).json({ error: err.message });
    if (!req.file) return res.status(400).json({ error: 'No se recibió ningún archivo' });

    const db = getDB();
    const existing = db.prepare('SELECT id FROM products WHERE id=?').get(req.params.id);
    if (!existing) return res.status(404).json({ error: 'Producto no encontrado' });

    const imageUrl = `/uploads/products/${req.file.filename}`;
    db.prepare('UPDATE products SET image_url=? WHERE id=?').run(imageUrl, req.params.id);

    res.json({ imageUrl });
  });
});

// ── GET /admin/logs ───────────────────────────────
router.get('/logs', (req, res) => {
  const db = getDB();
  const { action, page = 1, limit = 50 } = req.query;
  const offset = (parseInt(page) - 1) * parseInt(limit);

  let sql = `
    SELECT al.*, u.username as actor_username
    FROM audit_logs al
    LEFT JOIN users u ON u.id=al.user_id
    WHERE 1=1
  `;
  const params = [];
  if (action) { sql += ` AND al.action LIKE ?`; params.push(`%${action}%`); }
  sql += ` ORDER BY al.created_at DESC LIMIT ? OFFSET ?`;
  params.push(parseInt(limit), offset);

  const logs  = db.prepare(sql).all(...params);
  const total = db.prepare('SELECT COUNT(*) as n FROM audit_logs').get().n;
  res.json({ logs, total });
});

// ── GET /admin/reviews ────────────────────────────
router.get('/reviews', (_req, res) => {
  const db = getDB();
  const reviews = db.prepare(`
    SELECT r.*, u.username, p.name as product_name
    FROM reviews r
    JOIN users u    ON u.id=r.user_id
    JOIN products p ON p.id=r.product_id
    ORDER BY r.created_at DESC LIMIT 50
  `).all();
  res.json({ reviews });
});

// ═══════════════════════════════════════════════════════════════════════════════
// BOT POOL ADMIN ROUTES
// ═══════════════════════════════════════════════════════════════════════════════

// ── GET /admin/bots — todos los bots rentados por usuarios ───────────────────
router.get('/bots', (req, res) => {
  const db = getDB();
  const { status, user, page = 1, limit = 50 } = req.query;
  const offset = (parseInt(page) - 1) * parseInt(limit);

  let sql = `
    SELECT b.*, u.username, u.email
    FROM bots b
    JOIN users u ON u.id = b.user_id
    WHERE 1=1
  `;
  const params = [];
  if (status) { sql += ` AND b.status=?`;     params.push(status); }
  if (user)   { sql += ` AND (u.username LIKE ? OR u.email LIKE ?)`; params.push(`%${user}%`, `%${user}%`); }
  sql += ` ORDER BY b.created_at DESC LIMIT ? OFFSET ?`;
  params.push(parseInt(limit), offset);

  const bots  = db.prepare(sql).all(...params);
  const total = db.prepare('SELECT COUNT(*) as n FROM bots').get().n;
  const stats = {
    total,
    online:  db.prepare("SELECT COUNT(*) as n FROM bots WHERE status='online'").get().n,
    offline: db.prepare("SELECT COUNT(*) as n FROM bots WHERE status='offline'").get().n,
    expired: db.prepare("SELECT COUNT(*) as n FROM bots WHERE expires_at < datetime('now')").get().n,
  };
  res.json({ bots, total, stats, page: parseInt(page) });
});

// ── DELETE /admin/bots/:id — forzar eliminación de bot ──────────────────────
router.delete('/bots/:id', async (req, res, next) => {
  try {
    const db  = getDB();
    const bot = db.prepare('SELECT * FROM bots WHERE id=?').get(req.params.id);
    if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });

    // Liberar en el VPS (ignorar errores)
    try { await sendVPSCommand('destroy', { botId: bot.id }); } catch {}

    db.prepare('DELETE FROM bots WHERE id=?').run(bot.id);

    db.prepare(`INSERT INTO audit_logs (id,user_id,action,target_id,details) VALUES (?,?,?,?,?)`)
      .run(uuid(), req.user.id, 'admin_bot_delete', bot.id,
           JSON.stringify({ botName: bot.name, userId: bot.user_id }));

    notify(bot.user_id, { type:'warning', title:'Bot eliminado', message:`El bot "${bot.name}" fue eliminado por un administrador.` });
    res.json({ message: `Bot "${bot.name}" eliminado` });
  } catch (err) { next(err); }
});

// ── PATCH /admin/bots/:id — forzar estado / extender expiración ──────────────
router.patch('/bots/:id', async (req, res, next) => {
  try {
    const db  = getDB();
    const bot = db.prepare('SELECT * FROM bots WHERE id=?').get(req.params.id);
    if (!bot) return res.status(404).json({ error: 'Bot no encontrado' });

    const { status, expires_at, extend_days } = req.body;

    if (status && ['online','offline','busy','error'].includes(status)) {
      db.prepare("UPDATE bots SET status=?, updated_at=datetime('now') WHERE id=?").run(status, bot.id);
      if (status === 'online')  try { await sendVPSCommand('start',   { botId: bot.id }); } catch {}
      if (status === 'offline') try { await sendVPSCommand('stop',    { botId: bot.id }); } catch {}
    }

    if (extend_days && parseInt(extend_days) > 0) {
      const days    = parseInt(extend_days);
      const current = bot.expires_at ? new Date(bot.expires_at) : new Date();
      const newExp  = new Date(Math.max(current, Date.now()) + days * 86400000).toISOString();
      db.prepare("UPDATE bots SET expires_at=?, updated_at=datetime('now') WHERE id=?").run(newExp, bot.id);
      notify(bot.user_id, { type:'success', title:'Bot extendido', message:`Tu bot "${bot.name}" ha sido extendido ${days} días por el admin.` });
    }

    if (expires_at) {
      db.prepare("UPDATE bots SET expires_at=? WHERE id=?").run(expires_at, bot.id);
    }

    db.prepare(`INSERT INTO audit_logs (id,user_id,action,target_id,details) VALUES (?,?,?,?,?)`)
      .run(uuid(), req.user.id, 'admin_bot_update', bot.id, JSON.stringify(req.body));

    const updated = db.prepare('SELECT * FROM bots WHERE id=?').get(bot.id);
    res.json({ bot: updated });
  } catch (err) { next(err); }
});

// ── GET /admin/vps-status — estado del headless_bot_manager ─────────────────
router.get('/vps-status', async (_req, res) => {
  const VPS_URL = process.env.BOT_VPS_URL || 'http://localhost:5001';
  const GUI_URL = process.env.BOT_GUI_URL || 'http://localhost:5000';

  async function ping(url, name) {
    try {
      const r = await fetch(`${url}/health`, { signal: AbortSignal.timeout(3000) });
      const d = r.ok ? await r.json() : null;
      return { name, url, online: r.ok, data: d };
    } catch {
      return { name, url, online: false, data: null };
    }
  }

  const [headless, guiPanel] = await Promise.all([
    ping(VPS_URL, 'headless_bot_manager (5001)'),
    ping(GUI_URL, 'web.py panel (5000)'),
  ]);

  // Pool stats desde headless
  let pool = null;
  if (headless.online) {
    try {
      const r = await fetch(`${VPS_URL}/api/bots`, { signal: AbortSignal.timeout(3000) });
      pool = await r.json();
    } catch {}
  }

  const db = getDB();
  const dbBots = {
    total:   db.prepare('SELECT COUNT(*) as n FROM bots').get().n,
    active:  db.prepare("SELECT COUNT(*) as n FROM bots WHERE status='online'").get().n,
    expired: db.prepare("SELECT COUNT(*) as n FROM bots WHERE expires_at < datetime('now')").get().n,
  };

  res.json({ headless, guiPanel, pool, dbBots });
});

// ── POST /admin/vps/command — enviar comando directo al VPS ──────────────────
router.post('/vps/command', async (req, res, next) => {
  try {
    const { command, botId, ...rest } = req.body;
    if (!command) return res.status(400).json({ error: 'Falta command' });

    const result = await sendVPSCommand(command, { botId, ...rest });

    db_audit: {
      try {
        const db = getDB();
        db.prepare(`INSERT INTO audit_logs (id,user_id,action,target_id,details) VALUES (?,?,?,?,?)`)
          .run(uuid(), req.user.id, 'admin_vps_command', botId || 'pool',
               JSON.stringify({ command, ...rest }));
      } catch {}
    }

    res.json({ ok: true, result });
  } catch (err) { next(err); }
});

// ── POST /admin/vps/pool-action — acciones masivas sobre el pool ──────────────
router.post('/vps/pool-action', async (req, res, next) => {
  try {
    const { action } = req.body;  // 'stop-all' | 'status-all'
    const VPS_URL = process.env.BOT_VPS_URL || 'http://localhost:5001';
    const KEY     = process.env.BOT_VPS_API_KEY || '';

    const r = await fetch(`${VPS_URL}/api/bots`, { signal: AbortSignal.timeout(5000) });
    const bots = r.ok ? await r.json() : [];

    let results = [];
    if (action === 'stop-all') {
      for (const bot of bots.filter(b => b.status === 'online' || b.status === 'connecting')) {
        try {
          await fetch(`${VPS_URL}/api/bots/${bot.index}/stop`, {
            method: 'POST',
            headers: { 'X-Api-Key': KEY },
            signal: AbortSignal.timeout(3000),
          });
          results.push({ index: bot.index, ok: true });
        } catch (e) { results.push({ index: bot.index, ok: false, error: e.message }); }
      }
    }

    res.json({ action, bots: bots.length, results });
  } catch (err) { next(err); }
});

// ── GET /admin/users/:id/role — cambiar rol rápido ───────────────────────────
router.post('/users/:id/set-role', (req, res) => {
  const { role } = req.body;
  if (!['user','moderator','admin'].includes(role))
    return res.status(400).json({ error: 'Rol inválido: user | moderator | admin' });
  if (req.user.role !== 'admin')
    return res.status(403).json({ error: 'Solo admin puede cambiar roles' });

  const db   = getDB();
  const user = db.prepare('SELECT * FROM users WHERE id=?').get(req.params.id);
  if (!user) return res.status(404).json({ error: 'Usuario no encontrado' });

  db.prepare('UPDATE users SET role=? WHERE id=?').run(role, req.params.id);
  db.prepare(`INSERT INTO audit_logs (id,user_id,action,target_id,details) VALUES (?,?,?,?,?)`)
    .run(uuid(), req.user.id, 'admin_role_change', req.params.id, JSON.stringify({ from: user.role, to: role }));

  notify(req.params.id, { type: role === 'admin' ? 'success' : 'info', title: 'Rol actualizado', message: `Tu rol ha sido cambiado a: ${role}` });
  res.json({ message: `${user.username} → ${role}`, userId: req.params.id, role });
});

export default router;
