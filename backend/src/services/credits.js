import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';

/**
 * Deduce créditos de un usuario (bot_charge, service, etc.)
 * Lanza error si no hay saldo suficiente.
 */
export function chargeCredits(userId, amount, description, type = 'bot_charge', refOrderId = null) {
  const db   = getDB();
  const user = db.prepare('SELECT credits FROM users WHERE id = ?').get(userId);

  if (!user) throw new Error('Usuario no encontrado');
  if (user.credits < amount) {
    throw Object.assign(
      new Error(`Créditos insuficientes: necesitas ${amount}, tienes ${user.credits}`),
      { status: 402 }
    );
  }

  const newBalance = user.credits - amount;

  db.transaction(() => {
    db.prepare("UPDATE users SET credits = ?, updated_at = datetime('now') WHERE id = ?")
      .run(newBalance, userId);
    db.prepare(`
      INSERT INTO credit_transactions
        (id, user_id, type, amount, balance_after, description, ref_order_id)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(uuid(), userId, type, -amount, newBalance, description, refOrderId);
    // Actualizar stats
    db.prepare(`
      INSERT INTO user_stats (user_id, total_credits_spent)
      VALUES (?, ?)
      ON CONFLICT(user_id) DO UPDATE SET
        total_credits_spent = total_credits_spent + ?,
        updated_at = datetime('now')
    `).run(userId, amount, amount);
  })();

  return newBalance;
}

/**
 * Añade créditos a un usuario (compra, bono, recompensa, ajuste admin)
 */
export function addCredits(userId, amount, description, type = 'purchase', method = null, ref = null) {
  const db   = getDB();
  const user = db.prepare('SELECT credits FROM users WHERE id = ?').get(userId);
  if (!user) throw new Error('Usuario no encontrado');

  const newBalance = (user.credits || 0) + amount;

  db.transaction(() => {
    db.prepare("UPDATE users SET credits = ?, updated_at = datetime('now') WHERE id = ?")
      .run(newBalance, userId);
    db.prepare(`
      INSERT INTO credit_transactions
        (id, user_id, type, amount, balance_after, description, payment_method, payment_ref)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(uuid(), userId, type, amount, newBalance, description, method, ref);
    // Actualizar stats
    db.prepare(`
      INSERT INTO user_stats (user_id, total_credits_earned)
      VALUES (?, ?)
      ON CONFLICT(user_id) DO UPDATE SET
        total_credits_earned = total_credits_earned + ?,
        updated_at = datetime('now')
    `).run(userId, amount, amount);
  })();

  return newBalance;
}
