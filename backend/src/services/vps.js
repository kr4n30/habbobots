/**
 * vps.js — Comunicación con el headless_bot_manager.py
 *
 * Endpoints del bot manager:
 *   POST /command  → spawn | start | stop | destroy | status  (gestión de bots alquilados)
 *   POST /service  → room_fill | badge_respect | badge_pet | raid  (ejecución de servicios)
 *   POST /service/stop → libera bots de un pedido
 */

function _headers() {
  return {
    'Content-Type': 'application/json',
    'X-Api-Key':    process.env.BOT_VPS_API_KEY || '',
  };
}

function _baseUrl() {
  return process.env.BOT_VPS_URL;
}

// ── Gestión de bots alquilados ────────────────────────────────────────────────
// commands: spawn | start | stop | destroy | status
export async function sendVPSCommand(command, payload) {
  const url = _baseUrl();
  if (!url || !process.env.BOT_VPS_API_KEY) {
    console.warn('[VPS] BOT_VPS_URL o BOT_VPS_API_KEY no configurados — comando ignorado:', command);
    return { ok: false, stub: true };
  }

  const res = await fetch(`${url}/command`, {
    method:  'POST',
    headers: _headers(),
    body:    JSON.stringify({ command, ...payload }),
    signal:  AbortSignal.timeout(10_000),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`VPS /command error ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Ejecución de un servicio de la tienda ─────────────────────────────────────
// Llama a POST /service con los datos del pedido + producto
export async function sendVPSService(order, product) {
  const url = _baseUrl();
  if (!url || !process.env.BOT_VPS_API_KEY) {
    console.warn('[VPS] BOT_VPS_URL no configurado — servicio ignorado:', product.type);
    return { ok: false, stub: true };
  }

  // Mapear bot_count según tipo de producto
  let botCount = order.bot_count || 1;
  if (product.type === 'badge_respect') botCount = order.bot_count || 10;
  if (product.type === 'badge_pet')     botCount = order.bot_count || 5;

  const body = {
    type:            product.type,           // room_fill | badge_respect | badge_pet | raid
    orderId:         order.id,
    hotel:           order.hotel,
    habboName:       order.habbo_name,
    roomId:          order.room_id   || null,
    botCount:        botCount,
    durationSeconds: order.ends_at
      ? Math.max(0, Math.floor((new Date(order.ends_at) - Date.now()) / 1000))
      : (product.duration || 0),
  };

  const res = await fetch(`${url}/service`, {
    method:  'POST',
    headers: _headers(),
    body:    JSON.stringify(body),
    signal:  AbortSignal.timeout(15_000),
  });

  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`VPS /service error ${res.status}: ${errBody}`);
  }
  return res.json();
}

// ── Detener/liberar los bots de un pedido completado o cancelado ──────────────
export async function sendVPSServiceStop(orderId) {
  const url = _baseUrl();
  if (!url || !process.env.BOT_VPS_API_KEY) return { ok: false, stub: true };

  try {
    const res = await fetch(`${url}/service/stop`, {
      method:  'POST',
      headers: _headers(),
      body:    JSON.stringify({ orderId }),
      signal:  AbortSignal.timeout(8_000),
    });
    return res.ok ? res.json() : { ok: false };
  } catch (e) {
    console.warn('[VPS] /service/stop falló:', e.message);
    return { ok: false };
  }
}
