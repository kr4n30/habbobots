// ───────────────────────────────────────────────
//  HabboBots — Web Push (PWA) Service
//  Usa web-push con VAPID keys del .env
// ───────────────────────────────────────────────
import webpush from 'web-push';
import { getDB } from '../database/init.js';

let _init = false;

function ensureInit() {
  if (_init) return;
  const pub  = process.env.VAPID_PUBLIC_KEY;
  const priv = process.env.VAPID_PRIVATE_KEY;
  const mail = process.env.VAPID_EMAIL || `mailto:${process.env.SMTP_USER || 'admin@habbobots.com'}`;
  if (!pub || !priv) return; // sin claves VAPID, las notificaciones no funcionan
  webpush.setVapidDetails(mail, pub, priv);
  _init = true;
}

/** Enviar push a todas las suscripciones de un usuario */
export async function sendPushToUser(userId, { title, body, url = '/', icon = '/icons/icon-192.png' }) {
  ensureInit();
  if (!_init) return;

  const db   = getDB();
  const subs = db.prepare('SELECT * FROM push_subscriptions WHERE user_id = ?').all(userId);

  const payload = JSON.stringify({ title, body, url, icon });

  await Promise.allSettled(
    subs.map(async s => {
      try {
        await webpush.sendNotification({
          endpoint: s.endpoint,
          keys: { p256dh: s.p256dh, auth: s.auth },
        }, payload);
      } catch (e) {
        // Suscripción inválida → eliminar
        if (e.statusCode === 404 || e.statusCode === 410) {
          db.prepare('DELETE FROM push_subscriptions WHERE endpoint = ?').run(s.endpoint);
        }
      }
    })
  );
}

/** Obtener VAPID public key (para el frontend) */
export function getVapidPublicKey() {
  return process.env.VAPID_PUBLIC_KEY || null;
}
