import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';

/**
 * Deduct credits from a user (bot charge, etc.)
 * Throws if insufficient balance.
 */
export function chargeCredits(userId, amount, description) {
  const db   = getDB();
  const user = db.prepare('SELECT credits FROM users WHERE id = ?').get(userId);

  if (!user) throw new Error('Usuario no encontrado');
  if (user.credits < amount) {
    throw Object.assign(new Error(`Créditos insuficientes: necesitas ${amount}, tienes ${user.credits}`), { status: 402 });
  }

  const newBalance = user.credits - amount;

  const deductAndLog = db.transaction(() => {
    db.prepare("UPDATE users SET credits = ?, updated_at = datetime('now') WHERE id = ?").run(newBalance, userId);
    db.prepare(`
      INSERT INTO credit_transactions (id, user_id, type, amount, balance_after, description)
      VALUES (?, ?, 'bot_charge', ?, ?, ?)
    `).run(uuid(), userId, -amount, newBalance, description);
  });

  deductAndLog();
  return newBalance;
}

/**
 * Add credits to a user (purchase, bonus, refund)
 */
export function addCredits(userId, amount, description, type = 'purchase', method = null, ref = null) {
  const db   = getDB();
  const user = db.prepare('SELECT credits FROM users WHERE id = ?').get(userId);
  if (!user) throw new Error('Usuario no encontrado');

  const newBalance = (user.credits || 0) + amount;

  const addAndLog = db.transaction(() => {
    db.prepare("UPDATE users SET credits = ?, updated_at = datetime('now') WHERE id = ?").run(newBalance, userId);
    db.prepare(`
      INSERT INTO credit_transactions (id, user_id, type, amount, balance_after, description, payment_method, payment_ref)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(uuid(), userId, type, amount, newBalance, description, method, ref);
  });

  addAndLog();
  return newBalance;
}
