// ───────────────────────────────────────────────
//  HabboBots — Socket.io service
//  Emite notificaciones en tiempo real a usuarios
// ───────────────────────────────────────────────

import { Server as SocketServer } from 'socket.io';
import { getDB } from '../database/init.js';
import { v4 as uuid } from 'uuid';

let io = null;

export function initSocket(httpServer) {
  io = new SocketServer(httpServer, {
    cors: {
      origin: process.env.FRONTEND_URL || 'http://localhost:4321',
      methods: ['GET', 'POST'],
      credentials: true,
    },
    path: '/socket.io',
  });

  io.on('connection', (socket) => {
    // El cliente envía su userId tras conectar
    socket.on('join', (userId) => {
      if (!userId) return;
      socket.join(`user-${userId}`);
      // Enviar notificaciones no leídas pendientes
      flushPendingNotifications(userId, socket);
    });

    socket.on('disconnect', () => {});
  });

  console.log('🔌 Socket.io inicializado');
  return io;
}

export function getIO() {
  return io;
}

// ── Guardar + emitir notificación ─────────────────
export function notify(userId, { type = 'info', title, message, data = {} }) {
  const db  = getDB();
  const nid = uuid();
  try {
    db.prepare(`
      INSERT INTO notifications (id, user_id, type, title, message, data)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(nid, userId, type, title, message || null, JSON.stringify(data));
  } catch {}

  if (io) {
    io.to(`user-${userId}`).emit('notification', {
      id: nid, type, title, message, data, created_at: new Date().toISOString(),
    });
  }
}

// ── Emite actualización de pedido ─────────────────
export function notifyOrderUpdate(userId, order) {
  const statusLabels = {
    pending:   'en cola',
    active:    'en proceso',
    completed: '¡completado!',
    failed:    'fallido',
    cancelled: 'cancelado',
  };
  notify(userId, {
    type:    order.status === 'completed' ? 'success' : order.status === 'failed' ? 'danger' : 'info',
    title:   `Pedido ${statusLabels[order.status] || order.status}`,
    message: `${order.product_name || 'Servicio'} → ${order.habbo_name}@habbo.${order.hotel}`,
    data:    { orderId: order.id, status: order.status },
  });

  // También emite evento específico para actualizar UI sin recargar
  if (io) {
    io.to(`user-${userId}`).emit('order_update', order);
  }
}

// ── Emite créditos actualizados ───────────────────
export function notifyCreditsUpdate(userId, balance) {
  if (io) {
    io.to(`user-${userId}`).emit('credits_update', { balance });
  }
}

// ── Enviar pendientes al reconectar ──────────────
function flushPendingNotifications(userId, socket) {
  const db = getDB();
  try {
    const unread = db.prepare(`
      SELECT * FROM notifications
      WHERE user_id = ? AND read = 0
      ORDER BY created_at DESC LIMIT 20
    `).all(userId);

    if (unread.length > 0) {
      socket.emit('pending_notifications', unread);
    }
  } catch {}
}
