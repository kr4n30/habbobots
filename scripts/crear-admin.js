#!/usr/bin/env node
/**
 * crear-admin.js — Crea o promueve un usuario a admin en la BD SQLite
 *
 * USO (desde la raíz del proyecto):
 *   node scripts/crear-admin.js                          ← crea admin@habbobots.com / admin123
 *   node scripts/crear-admin.js tu@email.com contraseña  ← usuario personalizado
 *   node scripts/crear-admin.js --promote email@x.com    ← promueve usuario existente a admin
 *
 * La base de datos se lee de backend/.env → DB_PATH, o por defecto:
 *   backend/data/habbobots.db
 */

import Database from 'better-sqlite3';
import bcrypt   from 'bcryptjs';
import { randomUUID } from 'crypto';
import { readFileSync, existsSync, mkdirSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT      = path.resolve(__dirname, '..');

// ── Leer DB_PATH del .env del backend ────────────────────────────────────────
function readEnvVar(varName) {
  const envFile = path.join(ROOT, 'backend', '.env');
  if (!existsSync(envFile)) return null;
  const lines = readFileSync(envFile, 'utf8').split('\n');
  for (const line of lines) {
    const [k, ...rest] = line.split('=');
    if (k.trim() === varName) return rest.join('=').trim();
  }
  return null;
}

const rawDbPath = readEnvVar('DB_PATH') || './data/habbobots.db';
const DB_PATH   = path.isAbsolute(rawDbPath)
  ? rawDbPath
  : path.resolve(ROOT, 'backend', rawDbPath);

// ── Asegurarse de que el directorio existe ────────────────────────────────────
mkdirSync(path.dirname(DB_PATH), { recursive: true });

const db = new Database(DB_PATH);

// ── Parsear argumentos ────────────────────────────────────────────────────────
const args = process.argv.slice(2);

if (args[0] === '--promote') {
  // Promover usuario existente
  const email = args[1];
  if (!email) {
    console.error('USO: node scripts/crear-admin.js --promote email@usuario.com');
    process.exit(1);
  }
  const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
  if (!user) {
    console.error(`✗ No existe ningún usuario con email: ${email}`);
    process.exit(1);
  }
  db.prepare("UPDATE users SET role='admin', email_verified=1 WHERE email=?").run(email);
  console.log(`✓ ${user.username} (${email}) promovido a ADMIN`);
  process.exit(0);
}

// ── Crear usuario admin ───────────────────────────────────────────────────────
const email    = args[0] || 'admin@habbobots.com';
const password = args[1] || 'admin123';
const username = args[2] || 'Admin';

// Comprobar si ya existe
const existing = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
if (existing) {
  if (existing.role === 'admin') {
    console.log(`ℹ️  El usuario ${email} ya es admin.`);
    console.log(`   Usuario: ${existing.username}`);
  } else {
    db.prepare("UPDATE users SET role='admin', email_verified=1 WHERE email=?").run(email);
    console.log(`✓ ${existing.username} (${email}) promovido a ADMIN`);
  }
  process.exit(0);
}

// Hash de contraseña
const hash = bcrypt.hashSync(password, 12);
const id   = randomUUID();

db.prepare(`
  INSERT INTO users (id, email, username, password, role, credits, email_verified, created_at, updated_at)
  VALUES (?, ?, ?, ?, 'admin', 99999, 1, datetime('now'), datetime('now'))
`).run(id, email, username, hash);

// Stats iniciales
try {
  db.prepare(`INSERT INTO user_stats (user_id) VALUES (?)`).run(id);
} catch {}

console.log('');
console.log('✅  Admin creado correctamente');
console.log('──────────────────────────────────────');
console.log(`  Email    : ${email}`);
console.log(`  Password : ${password}`);
console.log(`  Username : ${username}`);
console.log(`  Créditos : 99.999`);
console.log(`  BD       : ${DB_PATH}`);
console.log('──────────────────────────────────────');
console.log('  Ahora puedes iniciar sesión en la web.');
console.log('');
