// ───────────────────────────────────────────────
//  HabboBots — Discord Webhook Service
//  Envía embeds a múltiples webhooks según tipo:
//    DISCORD_WEBHOOK_ORDERS   → pedidos / servicios
//    DISCORD_WEBHOOK_PAYMENTS → pagos / créditos
//    DISCORD_WEBHOOK_URL      → fallback genérico (legacy)
// ───────────────────────────────────────────────

const COLORS = {
  info:    0x00c3ff,
  success: 0x00ffa3,
  warning: 0xffbe00,
  danger:  0xff3c3c,
};

/**
 * Envía un embed de Discord a la(s) URL(s) indicadas.
 * @param {object}   embed   - Embed de Discord (title, description, color, fields, footer)
 * @param {string[]} targets - Array de variables de entorno con las webhook URLs
 */
export async function sendDiscord(embed, targets = ['DISCORD_WEBHOOK_URL']) {
  const urls = [...new Set(
    targets.map(k => process.env[k]).filter(Boolean)
  )];
  if (!urls.length) return;

  const body = JSON.stringify({ embeds: [embed] });
  await Promise.allSettled(
    urls.map(url =>
      fetch(url, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        signal:  AbortSignal.timeout(8_000),
      })
    )
  );
}

// ── Helpers preformateados ─────────────────────────────────────────────────────

/** Nuevo pedido creado por un usuario */
export function discordOrder(order, product) {
  return sendDiscord({
    title:       '🛒 Nuevo pedido',
    description: `**${product.name}** → **${order.habbo_name}** @ habbo.${order.hotel}`,
    color:       COLORS.info,
    fields: [
      { name: 'Créditos',  value: `${order.credits_paid} cr`,      inline: true },
      { name: 'Sala',      value: order.room_id    || '—',          inline: true },
      { name: 'Bots',      value: String(order.bot_count || '—'),   inline: true },
      { name: 'Notas',     value: order.notes      || '—',          inline: false },
    ],
    footer: { text: `Pedido ${order.id}` },
    timestamp: new Date().toISOString(),
  }, ['DISCORD_WEBHOOK_ORDERS', 'DISCORD_WEBHOOK_URL']);
}

/** Pedido activado */
export function discordOrderActivated(order, vpsResult) {
  return sendDiscord({
    title:       '🤖 Pedido iniciado',
    description: `**${order.product_name}** → **${order.habbo_name}** @ habbo.${order.hotel}`,
    color:       COLORS.info,
    fields: [
      { name: 'Créditos', value: `${order.credits_paid} cr`,                                  inline: true },
      { name: 'Sala',     value: order.room_id  || '—',                                       inline: true },
      { name: 'Bots',     value: String(order.bot_count || '—'),                              inline: true },
      { name: 'Notas',    value: order.notes    || '—',                                       inline: false },
      { name: 'VPS',      value: vpsResult?.stub ? '(sin VPS)' : `✅ ${vpsResult?.count || 0} bots`, inline: true },
    ],
    footer: { text: `Pedido ${order.id}` },
    timestamp: new Date().toISOString(),
  }, ['DISCORD_WEBHOOK_ORDERS', 'DISCORD_WEBHOOK_URL']);
}

/** Pedido completado */
export function discordOrderCompleted(order, duration) {
  return sendDiscord({
    title:       '✅ Pedido completado',
    description: `**${order.product_name}** → **${order.habbo_name}**`,
    color:       COLORS.success,
    fields: [{ name: 'Duración', value: duration || '—', inline: true }],
    footer: { text: `Pedido ${order.id}` },
    timestamp: new Date().toISOString(),
  }, ['DISCORD_WEBHOOK_ORDERS', 'DISCORD_WEBHOOK_URL']);
}

/** Pago recibido (PayPal / crypto / otro) */
export function discordPayment({ method, pack, credits, userId, amount }) {
  const methodLabel = { paypal: 'PayPal 💳', nowpayments: 'Crypto ₿', stripe: 'Stripe 💳', ingame: 'In-game 🎮' }[method] || method;
  return sendDiscord({
    title:       '💰 Pago recibido',
    description: `**${methodLabel}** — Pack **${pack}**`,
    color:       COLORS.success,
    fields: [
      { name: 'Créditos', value: `${credits} cr`,          inline: true },
      { name: 'Importe',  value: amount ? `€${amount}` : '—', inline: true },
      { name: 'Usuario',  value: userId,                   inline: true },
    ],
    timestamp: new Date().toISOString(),
  }, ['DISCORD_WEBHOOK_PAYMENTS', 'DISCORD_WEBHOOK_URL']);
}

/** Error crítico del sistema */
export function discordError(context, message) {
  return sendDiscord({
    title:       '🚨 Error del sistema',
    description: `**${context}**: ${message}`,
    color:       COLORS.danger,
    timestamp:   new Date().toISOString(),
  }, ['DISCORD_WEBHOOK_URL']);
}

/** Ticket de soporte abierto */
export function discordTicket({ id, subject, username, orderId }) {
  return sendDiscord({
    title:       '🎫 Nuevo ticket de soporte',
    description: `**${subject}**\nUsuario: **${username}**${orderId ? `\nPedido: \`${orderId}\`` : ''}`,
    color:       COLORS.warning,
    footer: { text: `Ticket ${id}` },
    timestamp: new Date().toISOString(),
  }, ['DISCORD_WEBHOOK_URL']);
}
