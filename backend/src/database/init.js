import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH   = process.env.DB_PATH || path.join(__dirname, '../../data/habbobots.db');

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

  -- ════════════════════════════════════════
  --  USUARIOS
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    username       TEXT UNIQUE NOT NULL,
    email          TEXT UNIQUE NOT NULL,
    password       TEXT,                          -- null para OAuth
    discord_id     TEXT UNIQUE,
    discord_tag    TEXT,
    avatar_url     TEXT,
    credits        INTEGER NOT NULL DEFAULT 0,
    role           TEXT NOT NULL DEFAULT 'user',  -- user | moderator | admin
    is_banned      INTEGER NOT NULL DEFAULT 0,
    ban_reason     TEXT,
    ban_expires    TEXT,                          -- null = permanente
    email_verified INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- ════════════════════════════════════════
  --  IDENTIDADES HABBO (uniqueId estable)
  --  Si el usuario cambia de nick, se añade al historial
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS habbo_identities (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hotel        TEXT NOT NULL,
    habbo_uid    TEXT NOT NULL,          -- uniqueId devuelto por la API de Habbo
    current_name TEXT NOT NULL,
    verified_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(hotel, habbo_uid)
  );

  CREATE TABLE IF NOT EXISTS habbo_name_history (
    id           TEXT PRIMARY KEY,
    identity_id  TEXT NOT NULL REFERENCES habbo_identities(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    seen_at      TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- Compatibilidad con el flujo de verificación por motto
  CREATE TABLE IF NOT EXISTS habbo_accounts (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hotel       TEXT NOT NULL,
    habbo_name  TEXT NOT NULL,
    verified_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, hotel)
  );

  -- ════════════════════════════════════════
  --  TOKENS DE VERIFICACIÓN (motto, TTL 10 min)
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS verify_tokens (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hotel      TEXT NOT NULL,
    token      TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
  );

  -- ════════════════════════════════════════
  --  BOTS
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS bots (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    hotel          TEXT NOT NULL,
    room           TEXT,
    status         TEXT NOT NULL DEFAULT 'offline',  -- online | offline | busy | error
    uptime_pct     REAL NOT NULL DEFAULT 0,
    actions        INTEGER NOT NULL DEFAULT 0,
    cost_per_month INTEGER NOT NULL DEFAULT 60,
    expires_at     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- ════════════════════════════════════════
  --  TIENDA — CATÁLOGO DE PRODUCTOS/SERVICIOS
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS products (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,
    type         TEXT NOT NULL,      -- badge_respect | badge_pet | room_fill | raid | trade | custom
    price        INTEGER NOT NULL,   -- créditos
    hotel        TEXT,               -- null = todos los hoteles
    duration     INTEGER,            -- segundos (para servicios con tiempo, null = instantáneo)
    max_quantity INTEGER,            -- veces máx que un usuario puede comprarlo, null = ilimitado
    active       INTEGER NOT NULL DEFAULT 1,
    sort_order   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- Pedidos de servicios (créditos gastados en la tienda)
  CREATE TABLE IF NOT EXISTS service_orders (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id   TEXT NOT NULL REFERENCES products(id),
    hotel        TEXT NOT NULL,
    habbo_name   TEXT NOT NULL,      -- personaje de Habbo que recibe el servicio
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending | active | completed | cancelled | failed
    credits_paid INTEGER NOT NULL,
    notes        TEXT,               -- parámetros adicionales (p.ej. duración personalizada)
    started_at   TEXT,
    ends_at      TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- ════════════════════════════════════════
  --  CRÉDITOS — TRANSACCIONES
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS credit_transactions (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type           TEXT NOT NULL,    -- purchase | bot_charge | service | refund | bonus | event_reward | admin_adjust
    amount         INTEGER NOT NULL,
    balance_after  INTEGER NOT NULL,
    description    TEXT,
    payment_method TEXT,             -- stripe | paypal | ingame
    payment_ref    TEXT,
    ref_order_id   TEXT,             -- service_orders.id si aplica
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- ════════════════════════════════════════
  --  REGISTRO PENDIENTE (pre-register, TTL 15 min)
  --  El usuario no existe en DB hasta que verifica el motto
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS pending_registrations (
    id         TEXT PRIMARY KEY,
    email      TEXT NOT NULL,
    password   TEXT NOT NULL,   -- ya hasheado
    code       TEXT NOT NULL,   -- HB-XXXXXX que debe poner como motto
    ip         TEXT,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- ════════════════════════════════════════
  --  TOKENS DE VERIFICACIÓN DE EMAIL (TTL 24h)
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS email_tokens (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      TEXT UNIQUE NOT NULL,
    expires_at TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- Refresh tokens JWT
  CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      TEXT UNIQUE NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- ════════════════════════════════════════
  --  CHAT
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS chat_messages (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel    TEXT NOT NULL DEFAULT 'global',  -- global | group:ID | dm:userID
    content    TEXT NOT NULL,
    deleted    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- ════════════════════════════════════════
  --  SISTEMA SOCIAL — SEGUIDORES / AMIGOS
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS user_follows (
    follower_id  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    following_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (follower_id, following_id)
  );

  -- Reputación (+rep / -rep, un voto por par de usuarios)
  CREATE TABLE IF NOT EXISTS reputation (
    id         TEXT PRIMARY KEY,
    from_user  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    value      INTEGER NOT NULL CHECK (value IN (1, -1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(from_user, to_user)
  );

  -- Stats agregadas por usuario (caché para leaderboards)
  CREATE TABLE IF NOT EXISTS user_stats (
    user_id              TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    total_services       INTEGER NOT NULL DEFAULT 0,
    total_credits_spent  INTEGER NOT NULL DEFAULT 0,
    total_credits_earned INTEGER NOT NULL DEFAULT 0,
    reputation_score     INTEGER NOT NULL DEFAULT 0,
    followers_count      INTEGER NOT NULL DEFAULT 0,
    bots_used            INTEGER NOT NULL DEFAULT 0,
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- ════════════════════════════════════════
  --  GRUPOS / FAMILIAS / MAFIAS
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS groups (
    id          TEXT PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    owner_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hotel       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS group_members (
    group_id   TEXT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT NOT NULL DEFAULT 'member',  -- owner | admin | member
    joined_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (group_id, user_id)
  );

  -- ════════════════════════════════════════
  --  EVENTOS CON RECOMPENSAS DE CRÉDITOS
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS events (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT,
    credit_reward  INTEGER NOT NULL DEFAULT 0,
    starts_at      TEXT NOT NULL,
    ends_at        TEXT NOT NULL,
    active         INTEGER NOT NULL DEFAULT 1,
    created_by     TEXT REFERENCES users(id),
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS event_participations (
    id         TEXT PRIMARY KEY,
    event_id   TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rewarded   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(event_id, user_id)
  );

  -- ════════════════════════════════════════
  --  SEGURIDAD — LOGS & ANTI-CHEAT
  -- ════════════════════════════════════════

  -- Log de IPs por acción (login, register, api_call)
  CREATE TABLE IF NOT EXISTS ip_logs (
    id         TEXT PRIMARY KEY,
    user_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
    ip         TEXT NOT NULL,
    action     TEXT NOT NULL,
    user_agent TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- Fingerprints de navegador (anti-multiaccount)
  CREATE TABLE IF NOT EXISTS fingerprints (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, fingerprint)
  );

  -- Log de auditoría general (trades, acciones admin, etc.)
  CREATE TABLE IF NOT EXISTS audit_logs (
    id         TEXT PRIMARY KEY,
    user_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
    action     TEXT NOT NULL,   -- user_ban | credit_adjust | order_cancel | etc.
    target_id  TEXT,            -- ID del recurso afectado
    details    TEXT,            -- JSON con detalles
    ip         TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- Bans (admin)
  CREATE TABLE IF NOT EXISTS bans (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason     TEXT,
    banned_by  TEXT REFERENCES users(id),
    expires_at TEXT,            -- null = permanente
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- ════════════════════════════════════════
  --  ÍNDICES PARA RENDIMIENTO
  -- ════════════════════════════════════════

  CREATE INDEX IF NOT EXISTS idx_bots_user       ON bots(user_id);
  CREATE INDEX IF NOT EXISTS idx_bots_status     ON bots(status);
  CREATE INDEX IF NOT EXISTS idx_orders_user     ON service_orders(user_id);
  CREATE INDEX IF NOT EXISTS idx_orders_status   ON service_orders(status);
  CREATE INDEX IF NOT EXISTS idx_chat_channel    ON chat_messages(channel, created_at);
  CREATE INDEX IF NOT EXISTS idx_txn_user        ON credit_transactions(user_id, created_at);
  CREATE INDEX IF NOT EXISTS idx_ip_logs_ip      ON ip_logs(ip, created_at);
  CREATE INDEX IF NOT EXISTS idx_audit_user      ON audit_logs(user_id, created_at);
  CREATE INDEX IF NOT EXISTS idx_habbo_uid       ON habbo_identities(hotel, habbo_uid);

  -- ════════════════════════════════════════
  --  RESEÑAS DE SERVICIOS
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS reviews (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id   TEXT NOT NULL REFERENCES service_orders(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES products(id),
    rating     INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    comment    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, order_id)
  );

  CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);

  -- ════════════════════════════════════════
  --  NOTIFICACIONES (persistidas para reconexión)
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS notifications (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       TEXT NOT NULL DEFAULT 'info',
    title      TEXT NOT NULL,
    message    TEXT,
    read       INTEGER NOT NULL DEFAULT 0,
    data       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, read, created_at);

  -- ════════════════════════════════════════
  --  PAGOS (PayPal / Crypto / Stripe)
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS payments (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pack_id      TEXT NOT NULL,
    method       TEXT NOT NULL,          -- paypal | nowpayments | stripe | ingame
    amount_eur   REAL,                   -- precio en EUR
    credits      INTEGER NOT NULL,       -- créditos a entregar
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending | completed | failed | expired
    external_id  TEXT,                   -- PayPal order ID / NOWPayments payment_id
    pay_address  TEXT,                   -- dirección crypto (NOWPayments)
    pay_amount   REAL,                   -- cantidad crypto exacta
    pay_currency TEXT,                   -- BTC / ETH / USDT ...
    return_url   TEXT,                   -- URL de retorno (PayPal)
    metadata     TEXT,                   -- JSON extra
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
  );

  CREATE INDEX IF NOT EXISTS idx_payments_user   ON payments(user_id, created_at);
  CREATE INDEX IF NOT EXISTS idx_payments_ext    ON payments(external_id);

  -- ════════════════════════════════════════
  --  AFILIADOS / REFERIDOS
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS affiliate_rewards (
    id           TEXT PRIMARY KEY,
    referrer_id  TEXT NOT NULL REFERENCES users(id),
    referred_id  TEXT NOT NULL REFERENCES users(id),
    credits_given INTEGER NOT NULL DEFAULT 0,
    reason       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- ════════════════════════════════════════
  --  SECRETOS 2FA (TOTP)
  -- ════════════════════════════════════════

  CREATE TABLE IF NOT EXISTS totp_secrets (
    user_id    TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    secret     TEXT NOT NULL,
    verified   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  `);

  // ── Migraciones para bases de datos existentes ────
  const migrations = [
    'ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0',
    'ALTER TABLE users ADD COLUMN last_seen_at TEXT',
    'ALTER TABLE users ADD COLUMN referral_code TEXT',
    'ALTER TABLE users ADD COLUMN referred_by TEXT',
    // Desactivar productos room_fill antiguos (sustituidos por prod_fill flexible)
    "UPDATE products SET active=0 WHERE id IN ('prod_roomfill_1h','prod_roomfill_6h')",
    // Llenar sala: precio base = 5 cr por bot-hora (frontend calcula precio total)
    `INSERT OR IGNORE INTO products (id,name,description,type,price,hotel,duration,max_quantity,active,sort_order)
     VALUES ('prod_fill','Llenar sala','Alquila bots para llenar tu sala. Elige duración (1h/6h/1d/3d) y cantidad de bots (5/10/20/50).','room_fill',5,NULL,NULL,NULL,1,5)`,
    // Truco Notas x20
    `INSERT OR IGNORE INTO products (id,name,description,type,price,hotel,duration,max_quantity,active,sort_order)
     VALUES ('prod_notas_20','Truco Notas x20','Los bots dejan 20 notas/stickers en tu habitación de Habbo.','custom',40,NULL,NULL,NULL,1,9)`,
    // Actualizar descripciones de caricias y respetos a precio fijo
    "UPDATE products SET description='10 respetos enviados a tu personaje. Precio fijo.' WHERE id='prod_respect_small'",
    "UPDATE products SET description='50 respetos enviados a tu personaje. Precio fijo.' WHERE id='prod_respect_big'",
    "UPDATE products SET description='10 caricias a tu mascota para subirle el nivel. Precio fijo.' WHERE id='prod_pet_small'",
    "UPDATE products SET description='50 caricias a tu mascota. Precio fijo.' WHERE id='prod_pet_big'",
    // Columna de etiqueta de duración en bots (ej: "1 semana", "3 meses")
    "ALTER TABLE bots ADD COLUMN duration_label TEXT",
    // Columnas extra en pedidos de servicios
    "ALTER TABLE service_orders ADD COLUMN room_id TEXT",
    "ALTER TABLE service_orders ADD COLUMN bot_count INTEGER",
    // Imagen de producto
    "ALTER TABLE products ADD COLUMN image_url TEXT",
    // Tabla de pagos
    `CREATE TABLE IF NOT EXISTS payments (
      id           TEXT PRIMARY KEY,
      user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      pack_id      TEXT NOT NULL,
      method       TEXT NOT NULL,
      amount_eur   REAL NOT NULL,
      credits      INTEGER NOT NULL,
      status       TEXT NOT NULL DEFAULT 'pending',
      external_id  TEXT,
      pay_address  TEXT,
      pay_amount   REAL,
      pay_currency TEXT,
      return_url   TEXT,
      metadata     TEXT,
      created_at   TEXT NOT NULL DEFAULT (datetime('now')),
      completed_at TEXT
    )`,
    "CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_ext  ON payments(external_id)",
    // Cupones de descuento
    `CREATE TABLE IF NOT EXISTS coupons (
      id           TEXT PRIMARY KEY,
      code         TEXT NOT NULL UNIQUE,
      discount_pct INTEGER NOT NULL DEFAULT 10,
      max_uses     INTEGER,
      uses         INTEGER NOT NULL DEFAULT 0,
      active       INTEGER NOT NULL DEFAULT 1,
      expires_at   TEXT,
      created_at   TEXT NOT NULL DEFAULT (datetime('now'))
    )`,
    // Tickets de soporte
    `CREATE TABLE IF NOT EXISTS tickets (
      id         TEXT PRIMARY KEY,
      user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      order_id   TEXT REFERENCES service_orders(id) ON DELETE SET NULL,
      subject    TEXT NOT NULL,
      status     TEXT NOT NULL DEFAULT 'open',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )`,
    `CREATE TABLE IF NOT EXISTS ticket_messages (
      id         TEXT PRIMARY KEY,
      ticket_id  TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
      user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      is_admin   INTEGER NOT NULL DEFAULT 0,
      message    TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )`,
    "CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_ticket_msgs  ON ticket_messages(ticket_id)",
    // Historial de actividad del bot
    `CREATE TABLE IF NOT EXISTS bot_logs (
      id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
      bot_id     TEXT NOT NULL,
      user_id    TEXT NOT NULL,
      action     TEXT NOT NULL,
      params     TEXT,
      result     TEXT,
      ok         INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )`,
    "CREATE INDEX IF NOT EXISTS idx_bot_logs_bot  ON bot_logs(bot_id)",
    "CREATE INDEX IF NOT EXISTS idx_bot_logs_user ON bot_logs(user_id)",
    // Incidencias para la status page
    `CREATE TABLE IF NOT EXISTS bot_incidents (
      id       TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
      title    TEXT NOT NULL,
      resolved INTEGER NOT NULL DEFAULT 0,
      at       TEXT NOT NULL DEFAULT (datetime('now'))
    )`,
    // Suscripciones push PWA
    `CREATE TABLE IF NOT EXISTS push_subscriptions (
      id           TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
      user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      endpoint     TEXT NOT NULL UNIQUE,
      p256dh       TEXT NOT NULL,
      auth         TEXT NOT NULL,
      created_at   TEXT NOT NULL DEFAULT (datetime('now'))
    )`,
    "CREATE INDEX IF NOT EXISTS idx_push_user ON push_subscriptions(user_id)",
    // IP de registro por usuario (1 cuenta por IP)
    "ALTER TABLE users ADD COLUMN registration_ip TEXT",
    "CREATE INDEX IF NOT EXISTS idx_users_regip ON users(registration_ip)",
  ];
  for (const sql of migrations) {
    try { db.exec(sql); } catch { /* ya aplicado o columna existe */ }
  }

  console.log('✅ Base de datos SQLite inicializada');

  // ── Seed productos por defecto ────────────────────
  seedDefaultProducts(db);
}

function seedDefaultProducts(db) {
  const count = db.prepare('SELECT COUNT(*) as n FROM products').get().n;
  if (count > 0) return; // ya hay productos, no repetir

  const products = [
    {
      id: 'prod_respect_small',
      name: 'Pack Respetos x10',
      description: 'Envía 10 respetos a tu personaje de Habbo.',
      type: 'badge_respect',
      price: 15,
      hotel: null,
      duration: null,
      max_quantity: null,
      sort_order: 1,
    },
    {
      id: 'prod_respect_big',
      name: 'Pack Respetos x50',
      description: 'Envía 50 respetos a tu personaje. ¡Sube en el ranking!',
      type: 'badge_respect',
      price: 60,
      hotel: null,
      duration: null,
      max_quantity: null,
      sort_order: 2,
    },
    {
      id: 'prod_pet_small',
      name: 'Caricias mascota x10',
      description: 'Acaricia tu mascota 10 veces para subirle el nivel.',
      type: 'badge_pet',
      price: 10,
      hotel: null,
      duration: null,
      max_quantity: null,
      sort_order: 3,
    },
    {
      id: 'prod_pet_big',
      name: 'Caricias mascota x50',
      description: 'Acaricia tu mascota 50 veces. ¡Llévala al máximo nivel!',
      type: 'badge_pet',
      price: 40,
      hotel: null,
      duration: null,
      max_quantity: null,
      sort_order: 4,
    },
    {
      id: 'prod_fill',
      name: 'Llenar sala',
      description: 'Alquila bots para llenar tu sala. Elige duración (1h/6h/1d/3d) y cantidad de bots (5/10/20/50).',
      type: 'room_fill',
      price: 5, // cr por bot-hora
      hotel: null,
      duration: null,
      max_quantity: null,
      sort_order: 5,
    },
    {
      id: 'prod_notas_20',
      name: 'Truco Notas x20',
      description: 'Los bots dejan 20 notas/stickers en tu habitación de Habbo.',
      type: 'custom',
      price: 40,
      hotel: null,
      duration: null,
      max_quantity: null,
      sort_order: 9,
    },
    {
      id: 'prod_raid',
      name: 'Raid a sala',
      description: 'Envía una oleada de bots a cualquier sala para animarla o desestabilizarla.',
      type: 'raid',
      price: 80,
      hotel: null,
      duration: 600,
      max_quantity: null,
      sort_order: 7,
    },
    {
      id: 'prod_trade',
      name: 'Trade automatizado',
      description: 'El bot gestiona un trade básico por ti en el hotel seleccionado.',
      type: 'trade',
      price: 30,
      hotel: null,
      duration: null,
      max_quantity: 5,
      sort_order: 8,
    },
  ];

  const insert = db.prepare(`
    INSERT OR IGNORE INTO products (id, name, description, type, price, hotel, duration, max_quantity, active, sort_order)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
  `);

  const insertAll = db.transaction(() => {
    for (const p of products) {
      insert.run(p.id, p.name, p.description, p.type, p.price, p.hotel, p.duration, p.max_quantity, p.sort_order);
    }
  });

  insertAll();
  console.log(`🛒 ${products.length} productos de catálogo insertados`);
}
