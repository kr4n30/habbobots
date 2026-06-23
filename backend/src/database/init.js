import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH   = process.env.DB_PATH || path.join(__dirname, '../../data/habbobots.db');

// Ensure data directory exists
fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

let db;

export function getDB() {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
  }
  return db;
}

export function initDB() {
  const db = getDB();

  db.exec(`
    -- Users
    CREATE TABLE IF NOT EXISTS users (
      id          TEXT PRIMARY KEY,
      username    TEXT UNIQUE NOT NULL,
      email       TEXT UNIQUE NOT NULL,
      password    TEXT,                          -- null for Discord OAuth users
      discord_id  TEXT UNIQUE,
      discord_tag TEXT,
      avatar_url  TEXT,
      credits     INTEGER NOT NULL DEFAULT 0,
      role        TEXT NOT NULL DEFAULT 'user',  -- user | admin
      created_at  TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Habbo verified accounts
    CREATE TABLE IF NOT EXISTS habbo_accounts (
      id          TEXT PRIMARY KEY,
      user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      hotel       TEXT NOT NULL,                 -- es | com | br | de | fi | it | nl
      habbo_name  TEXT NOT NULL,
      verified_at TEXT NOT NULL DEFAULT (datetime('now')),
      UNIQUE(user_id, hotel)
    );

    -- Motto verification tokens (TTL 10 min)
    CREATE TABLE IF NOT EXISTS verify_tokens (
      id         TEXT PRIMARY KEY,
      user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      hotel      TEXT NOT NULL,
      token      TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      used       INTEGER NOT NULL DEFAULT 0
    );

    -- Bots
    CREATE TABLE IF NOT EXISTS bots (
      id          TEXT PRIMARY KEY,
      user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      name        TEXT NOT NULL,
      hotel       TEXT NOT NULL,
      room        TEXT,
      status      TEXT NOT NULL DEFAULT 'offline',  -- online | offline | busy | error
      uptime_pct  REAL NOT NULL DEFAULT 0,
      actions     INTEGER NOT NULL DEFAULT 0,
      cost_per_month INTEGER NOT NULL DEFAULT 60,   -- credits
      expires_at  TEXT,
      created_at  TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Credit transactions
    CREATE TABLE IF NOT EXISTS credit_transactions (
      id          TEXT PRIMARY KEY,
      user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      type        TEXT NOT NULL,   -- purchase | bot_charge | refund | bonus
      amount      INTEGER NOT NULL,
      balance_after INTEGER NOT NULL,
      description TEXT,
      payment_method TEXT,         -- stripe | paypal | ingame
      payment_ref TEXT,            -- Stripe payment intent ID, etc.
      created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Sessions / refresh tokens
    CREATE TABLE IF NOT EXISTS refresh_tokens (
      id         TEXT PRIMARY KEY,
      user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      token      TEXT UNIQUE NOT NULL,
      expires_at TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
  `);

  console.log('✅ Base de datos inicializada');
}
