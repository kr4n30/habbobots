// ───────────────────────────────────────────────
//  HabboBots — Order Processor
//  Cola de trabajo: pending → active → completed
//  Conectado al headless_bot_manager.py vía VPS
// ───────────────────────────────────────────────

import { getDB } from '../database/init.js';
import { notifyOrderUpdate } from './socket.js';
import { addCredits } from './credits.js';
import { sendVPSService, sendVPSServiceStop } from './vps.js';
import { discordOrderActivated, discordOrderCompleted } from './discord.js';

// Intervalo de procesamiento (cada 20 segundos)
const POLL_INTERVAL_MS = 20_000;

// Tiempo mínimo desde la creación antes de activar un pedido (segundos)
const ACTIVATION_DELAY_S = 5;

export function startOrderProcessor() {
  console.log('⚙️  Procesador de pedidos iniciado');
  processOrders();
  setInterval(processOrders, POLL_INTERVAL_MS);
}

async function processOrders() {
  const db = getDB();

  // ── 1. pending → active ───────────────────────────────────────────────────
  const pendingOrders = db.prepare(`
    SELECT so.*, p.name as product_name, p.type as product_type,
           p.duration as product_duration
    FROM service_orders so
    JOIN products p ON p.id = so.product_id
    WHERE so.status = 'pending'
    AND so.created_at <= datetime('now', ? || ' seconds')
  `).all(`-${ACTIVATION_DELAY_S}`);

  for (const order of pendingOrders) {
    try {
      const product = { type: order.product_type, duration: order.product_duration };
      let vpsResult = { ok: false, stub: true };

      try {
        vpsResult = await sendVPSService(order, product);
      } catch (vpsErr) {
        console.error(`[OrderProcessor] VPS error en pedido ${order.id}:`, vpsErr.message);
        // No cancelamos — marcamos active de todas formas
      }

      db.prepare(`
        UPDATE service_orders
        SET status = 'active', started_at = datetime('now'), updated_at = datetime('now')
        WHERE id = ?
      `).run(order.id);

      const updated = db.prepare('SELECT * FROM service_orders WHERE id = ?').get(order.id);
      notifyOrderUpdate(order.user_id, {
        ...updated,
        product_name: order.product_name,
        vps: vpsResult,
      });

      discordOrderActivated(order, vpsResult);
    } catch (err) {
      console.error(`[OrderProcessor] Error activando pedido ${order.id}:`, err.message);
    }
  }

  // ── 2. active → completed (ends_at expirado) ─────────────────────────────
  const expiredOrders = db.prepare(`
    SELECT so.*, p.name as product_name, p.type as product_type
    FROM service_orders so
    JOIN products p ON p.id = so.product_id
    WHERE so.status = 'active'
    AND so.ends_at IS NOT NULL
    AND so.ends_at <= datetime('now')
  `).all();

  for (const order of expiredOrders) {
    try {
      await sendVPSServiceStop(order.id);

      db.prepare(`
        UPDATE service_orders
        SET status = 'completed', updated_at = datetime('now')
        WHERE id = ?
      `).run(order.id);

      const updated = db.prepare('SELECT * FROM service_orders WHERE id = ?').get(order.id);
      notifyOrderUpdate(order.user_id, { ...updated, product_name: order.product_name });

      discordOrderCompleted(order, formatDuration(order.started_at, order.ends_at));
    } catch (err) {
      console.error(`[OrderProcessor] Error completando pedido ${order.id}:`, err.message);
    }
  }

  // ── 3. active sin ends_at → completar tras 3 min (servicios instantáneos) ─
  const instantOrders = db.prepare(`
    SELECT so.*, p.name as product_name
    FROM service_orders so
    JOIN products p ON p.id = so.product_id
    WHERE so.status = 'active'
    AND so.ends_at IS NULL
    AND so.started_at <= datetime('now', '-3 minutes')
  `).all();

  for (const order of instantOrders) {
    try {
      await sendVPSServiceStop(order.id).catch(() => {});

      db.prepare(`
        UPDATE service_orders
        SET status = 'completed', updated_at = datetime('now')
        WHERE id = ?
      `).run(order.id);

      const updated = db.prepare('SELECT * FROM service_orders WHERE id = ?').get(order.id);
      notifyOrderUpdate(order.user_id, { ...updated, product_name: order.product_name });
    } catch (err) {
      console.error(`[OrderProcessor] Error completando pedido instantáneo ${order.id}:`, err.message);
    }
  }
}

// ── Reembolso automático si el servicio falla ────────────────────────────────
export async function refundOrder(orderId, reason = 'Servicio fallido') {
  const db    = getDB();
  const order = db.prepare('SELECT * FROM service_orders WHERE id = ?').get(orderId);
  if (!order || order.status === 'cancelled') return;

  db.prepare(`
    UPDATE service_orders SET status = 'cancelled', updated_at = datetime('now') WHERE id = ?
  `).run(orderId);

  if (order.credits_paid > 0) {
    addCredits(order.user_id, order.credits_paid, `Reembolso: ${reason}`, 'refund');
  }

  const updated = db.prepare('SELECT * FROM service_orders WHERE id = ?').get(orderId);
  notifyOrderUpdate(order.user_id, updated);
}


function formatDuration(start, end) {
  if (!start || !end) return '—';
  const diff = (new Date(end) - new Date(start)) / 1000;
  const h = Math.floor(diff / 3600);
  const m = Math.floor((diff % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
