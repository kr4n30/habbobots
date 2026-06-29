import jwt from 'jsonwebtoken';
import { getDB } from '../database/init.js';

if (!process.env.JWT_SECRET) {
  if (process.env.NODE_ENV === 'production') {
    console.error('[FATAL] JWT_SECRET no está definido. Configúralo en .env.');
    process.exit(1);
  } else {
    console.warn('[WARN] JWT_SECRET sin configurar — usando valor dev. ¡NO usar en producción!');
  }
}
const SECRET = process.env.JWT_SECRET || 'dev_secret_change_me';

export function generateAccessToken(userId) {
  return jwt.sign({ sub: userId }, SECRET, {
    expiresIn: process.env.JWT_EXPIRES_IN || '7d',
  });
}

export function requireAuth(req, res, next) {
  const header = req.headers.authorization;
  if (!header?.startsWith('Bearer '))
    return res.status(401).json({ error: 'Token requerido' });

  const token = header.slice(7);
  try {
    const payload = jwt.verify(token, SECRET);
    const db   = getDB();
    const user = db.prepare('SELECT * FROM users WHERE id = ?').get(payload.sub);
    if (!user)           return res.status(401).json({ error: 'Usuario no encontrado' });
    if (user.is_banned)  return res.status(403).json({ error: 'Cuenta suspendida', reason: user.ban_reason });
    req.user = user;
    // Actualiza last_seen_at sin bloquear la respuesta
    try {
      db.prepare("UPDATE users SET last_seen_at = datetime('now') WHERE id = ?").run(user.id);
    } catch {}
    next();
  } catch {
    return res.status(401).json({ error: 'Token inválido o expirado' });
  }
}

export function requireAdmin(req, res, next) {
  requireAuth(req, res, () => {
    if (req.user.role !== 'admin' && req.user.role !== 'moderator')
      return res.status(403).json({ error: 'Acceso denegado' });
    next();
  });
}
