// ───────────────────────────────────────────────
//  HabboBots — Support Tickets Routes
//
//  POST   /tickets                  → abrir ticket (usuario)
//  GET    /tickets/my               → mis tickets (usuario)
//  GET    /tickets/admin/all        → todos los tickets (admin)
//  GET    /tickets/:id              → detalle ticket + mensajes
//  POST   /tickets/:id/reply        → responder (usuario o admin)
//  PATCH  /tickets/:id/status       → cambiar estado (admin o usuario cierra propio)
// ───────────────────────────────────────────────

import { Router } from 'express';
import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';
import { requireAuth, requireAdmin } from '../middleware/auth.js';
import { discordTicket } from '../services/discord.js';

const router = Router();

// ── POST /tickets ──────────────────────────────
router.post('/', requireAuth, (req, res, next) => {
  try {
    const { subject, message, order_id } = req.body;
    if (!subject?.trim() || !message?.trim())
      return res.status(400).json({ error: 'subject y message son obligatorios' });

    const db       = getDB();
    const ticketId = uuid();
    const msgId    = uuid();

    // Verificar que el pedido pertenece al usuario si se proporciona
    if (order_id) {
      const order = db.prepare('SELECT id FROM service_orders WHERE id = ? AND user_id = ?').get(order_id, req.user.id);
      if (!order) return res.status(400).json({ error: 'Pedido no encontrado o no te pertenece' });
    }

    db.transaction(() => {
      db.prepare(`
        INSERT INTO tickets (id, user_id, order_id, subject, status)
        VALUES (?, ?, ?, ?, 'open')
      `).run(ticketId, req.user.id, order_id || null, subject.trim());

      db.prepare(`
        INSERT INTO ticket_messages (id, ticket_id, user_id, is_admin, message)
        VALUES (?, ?, ?, 0, ?)
      `).run(msgId, ticketId, req.user.id, message.trim());
    })();

    // Notificar Discord
    const user = db.prepare('SELECT username FROM users WHERE id = ?').get(req.user.id);
    discordTicket({ id: ticketId, subject: subject.trim(), username: user?.username || req.user.id, orderId: order_id }).catch(() => {});

    const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticketId);
    res.status(201).json({ ticket });
  } catch (err) { next(err); }
});

// ── GET /tickets/my ────────────────────────────
router.get('/my', requireAuth, (req, res) => {
  const db = getDB();
  const tickets = db.prepare(`
    SELECT t.*, u.username,
           (SELECT COUNT(*) FROM ticket_messages WHERE ticket_id = t.id) as message_count
    FROM tickets t
    JOIN users u ON u.id = t.user_id
    WHERE t.user_id = ?
    ORDER BY t.updated_at DESC
  `).all(req.user.id);
  res.json({ tickets });
});

// ── GET /tickets/admin/all ─────────────────────
router.get('/admin/all', requireAdmin, (req, res) => {
  const db = getDB();
  const { status } = req.query;
  let sql = `
    SELECT t.*, u.username,
           (SELECT COUNT(*) FROM ticket_messages WHERE ticket_id = t.id) as message_count
    FROM tickets t
    JOIN users u ON u.id = t.user_id
    WHERE 1=1
  `;
  const params = [];
  if (status) { sql += ' AND t.status = ?'; params.push(status); }
  sql += ' ORDER BY t.status ASC, t.updated_at DESC LIMIT 100';

  const tickets = db.prepare(sql).all(...params);
  res.json({ tickets });
});

// ── GET /tickets/:id ───────────────────────────
router.get('/:id', requireAuth, (req, res) => {
  const db = getDB();
  const ticket = db.prepare(`
    SELECT t.*, u.username FROM tickets t
    JOIN users u ON u.id = t.user_id
    WHERE t.id = ?
  `).get(req.params.id);

  if (!ticket) return res.status(404).json({ error: 'Ticket no encontrado' });

  // Solo el propietario o un admin puede verlo
  const isOwner = ticket.user_id === req.user.id;
  const isAdmin = ['admin', 'moderator'].includes(req.user.role);
  if (!isOwner && !isAdmin) return res.status(403).json({ error: 'Sin acceso' });

  const messages = db.prepare(`
    SELECT tm.*, u.username FROM ticket_messages tm
    JOIN users u ON u.id = tm.user_id
    WHERE tm.ticket_id = ?
    ORDER BY tm.created_at ASC
  `).all(req.params.id);

  res.json({ ticket, messages });
});

// ── POST /tickets/:id/reply ────────────────────
router.post('/:id/reply', requireAuth, (req, res, next) => {
  try {
    const { message } = req.body;
    if (!message?.trim()) return res.status(400).json({ error: 'message requerido' });

    const db     = getDB();
    const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(req.params.id);
    if (!ticket) return res.status(404).json({ error: 'Ticket no encontrado' });

    const isOwner = ticket.user_id === req.user.id;
    const isAdmin = ['admin', 'moderator'].includes(req.user.role);
    if (!isOwner && !isAdmin) return res.status(403).json({ error: 'Sin acceso' });
    if (ticket.status === 'closed') return res.status(400).json({ error: 'El ticket está cerrado' });

    const msgId = uuid();
    db.prepare(`
      INSERT INTO ticket_messages (id, ticket_id, user_id, is_admin, message)
      VALUES (?, ?, ?, ?, ?)
    `).run(msgId, ticket.id, req.user.id, isAdmin && !isOwner ? 1 : 0, message.trim());

    db.prepare("UPDATE tickets SET updated_at = datetime('now') WHERE id = ?").run(ticket.id);

    const msg = db.prepare('SELECT * FROM ticket_messages WHERE id = ?').get(msgId);
    res.status(201).json({ message: msg });
  } catch (err) { next(err); }
});

// ── PATCH /tickets/:id/status ──────────────────
router.patch('/:id/status', requireAuth, (req, res, next) => {
  try {
    const { status } = req.body;
    const validStatuses = ['open', 'closed', 'in_progress'];
    if (!validStatuses.includes(status))
      return res.status(400).json({ error: `Estado inválido. Válidos: ${validStatuses.join(', ')}` });

    const db     = getDB();
    const ticket = db.prepare('SELECT * FROM tickets WHERE id = ?').get(req.params.id);
    if (!ticket) return res.status(404).json({ error: 'Ticket no encontrado' });

    const isOwner = ticket.user_id === req.user.id;
    const isAdmin = ['admin', 'moderator'].includes(req.user.role);

    // Un usuario solo puede cerrar su propio ticket, no re-abrirlo
    if (!isAdmin) {
      if (!isOwner) return res.status(403).json({ error: 'Sin acceso' });
      if (status !== 'closed') return res.status(403).json({ error: 'Solo puedes cerrar tu ticket' });
    }

    db.prepare("UPDATE tickets SET status = ?, updated_at = datetime('now') WHERE id = ?")
      .run(status, ticket.id);

    res.json({ ticket: db.prepare('SELECT * FROM tickets WHERE id = ?').get(ticket.id) });
  } catch (err) { next(err); }
});

export default router;
