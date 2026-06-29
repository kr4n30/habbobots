"""
db.py — SQLite database para el Shop de Habbo Bot Manager
"""
import sqlite3, os, secrets, hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shop.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id  TEXT    UNIQUE NOT NULL,
            username    TEXT    NOT NULL,
            discriminator TEXT  DEFAULT '0',
            avatar      TEXT,
            email       TEXT,
            credits     INTEGER DEFAULT 0,
            is_admin    INTEGER DEFAULT 0,
            is_banned   INTEGER DEFAULT 0,
            created_at  TEXT    DEFAULT (datetime('now')),
            last_login  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS credit_packages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            credits     INTEGER NOT NULL,
            bonus       INTEGER DEFAULT 0,
            price_eur   REAL    NOT NULL,
            color       TEXT    DEFAULT '#30728C',
            tag         TEXT    DEFAULT '',
            is_active   INTEGER DEFAULT 1,
            sort_order  INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            type        TEXT    NOT NULL,  -- purchase|grant|consume|refund
            credits_delta INTEGER NOT NULL,
            credits_after INTEGER NOT NULL,
            description TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'pending',  -- pending|completed|rejected
            ref         TEXT    DEFAULT '',          -- payment ref, admin note, etc.
            package_id  INTEGER REFERENCES credit_packages(id),
            created_at  TEXT    DEFAULT (datetime('now')),
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            key_hash    TEXT    UNIQUE NOT NULL,
            key_prefix  TEXT    NOT NULL,
            name        TEXT    DEFAULT 'API Key',
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT    DEFAULT (datetime('now')),
            last_used   TEXT
        );

        CREATE TABLE IF NOT EXISTS bot_slots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            slot_label  TEXT    NOT NULL,
            credits_per_hour INTEGER DEFAULT 1,
            started_at  TEXT,
            stopped_at  TEXT,
            is_running  INTEGER DEFAULT 0
        );

        -- Paquetes por defecto
        INSERT OR IGNORE INTO credit_packages (id,name,credits,bonus,price_eur,color,tag,sort_order)
        VALUES
            (1,'Starter',  100,   0,  4.99, '#4a6a7a', '',            1),
            (2,'Pro',      500,   50, 17.99,'#1a7a3a', 'MÁS POPULAR', 2),
            (3,'Elite',   1500, 200,  44.99,'#6633aa', 'MEJOR VALOR', 3),
            (4,'Ultimate',5000, 800, 109.99,'#b85c00', 'VIP',         4);
        """)


# ── USERS ─────────────────────────────────────────────────────────────────────

def upsert_user(discord_id, username, discriminator='0', avatar=None, email=None):
    with get_db() as db:
        existing = db.execute('SELECT id FROM users WHERE discord_id=?', (discord_id,)).fetchone()
        if existing:
            db.execute(
                'UPDATE users SET username=?,discriminator=?,avatar=?,email=?,last_login=datetime("now") WHERE discord_id=?',
                (username, discriminator, avatar, email, discord_id)
            )
            return db.execute('SELECT * FROM users WHERE discord_id=?', (discord_id,)).fetchone()
        else:
            db.execute(
                'INSERT INTO users (discord_id,username,discriminator,avatar,email) VALUES (?,?,?,?,?)',
                (discord_id, username, discriminator, avatar, email)
            )
            return db.execute('SELECT * FROM users WHERE discord_id=?', (discord_id,)).fetchone()


def get_user(user_id):
    with get_db() as db:
        return db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()


def get_user_by_discord(discord_id):
    with get_db() as db:
        return db.execute('SELECT * FROM users WHERE discord_id=?', (discord_id,)).fetchone()


def all_users(limit=200, offset=0):
    with get_db() as db:
        return db.execute(
            'SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)
        ).fetchall()


def set_admin(user_id, is_admin=True):
    with get_db() as db:
        db.execute('UPDATE users SET is_admin=? WHERE id=?', (1 if is_admin else 0, user_id))


def ban_user(user_id, banned=True):
    with get_db() as db:
        db.execute('UPDATE users SET is_banned=? WHERE id=?', (1 if banned else 0, user_id))


# ── CREDITS ───────────────────────────────────────────────────────────────────

def add_credits(user_id, amount, description='', tx_type='grant', ref='', package_id=None, status='completed'):
    with get_db() as db:
        current = db.execute('SELECT credits FROM users WHERE id=?', (user_id,)).fetchone()
        if not current:
            return None
        new_bal = current['credits'] + amount
        if new_bal < 0:
            new_bal = 0
        db.execute('UPDATE users SET credits=? WHERE id=?', (new_bal, user_id))
        db.execute(
            'INSERT INTO transactions (user_id,type,credits_delta,credits_after,description,status,ref,package_id,resolved_at) VALUES (?,?,?,?,?,?,?,?,datetime("now"))',
            (user_id, tx_type, amount, new_bal, description, status, ref, package_id)
        )
        return new_bal


def consume_credits(user_id, amount, description='consume'):
    with get_db() as db:
        row = db.execute('SELECT credits FROM users WHERE id=?', (user_id,)).fetchone()
        if not row or row['credits'] < amount:
            return False, row['credits'] if row else 0
        new_bal = row['credits'] - amount
        db.execute('UPDATE users SET credits=? WHERE id=?', (new_bal, user_id))
        db.execute(
            'INSERT INTO transactions (user_id,type,credits_delta,credits_after,description,status,resolved_at) VALUES (?,?,?,?,?,?,datetime("now"))',
            (user_id, 'consume', -amount, new_bal, description, 'completed')
        )
        return True, new_bal


def get_transactions(user_id, limit=50):
    with get_db() as db:
        return db.execute(
            'SELECT t.*,p.name as pkg_name FROM transactions t LEFT JOIN credit_packages p ON t.package_id=p.id WHERE t.user_id=? ORDER BY t.created_at DESC LIMIT ?',
            (user_id, limit)
        ).fetchall()


def create_purchase_tx(user_id, package_id):
    pkg = get_package(package_id)
    if not pkg:
        return None
    total = pkg['credits'] + pkg['bonus']
    with get_db() as db:
        row = db.execute('SELECT credits FROM users WHERE id=?', (user_id,)).fetchone()
        cur = row['credits'] if row else 0
        db.execute(
            'INSERT INTO transactions (user_id,type,credits_delta,credits_after,description,status,package_id) VALUES (?,?,?,?,?,?,?)',
            (user_id, 'purchase', total, cur, f'Compra paquete {pkg["name"]}', 'pending', package_id)
        )
        return db.execute('SELECT last_insert_rowid() as id').fetchone()['id']


def approve_tx(tx_id, admin_ref=''):
    with get_db() as db:
        tx = db.execute('SELECT * FROM transactions WHERE id=? AND status="pending"', (tx_id,)).fetchone()
        if not tx:
            return False
        row = db.execute('SELECT credits FROM users WHERE id=?', (tx['user_id'],)).fetchone()
        new_bal = row['credits'] + tx['credits_delta']
        db.execute('UPDATE users SET credits=? WHERE id=?', (new_bal, tx['user_id']))
        db.execute(
            'UPDATE transactions SET status="completed",credits_after=?,ref=?,resolved_at=datetime("now") WHERE id=?',
            (new_bal, admin_ref, tx_id)
        )
        return True


def reject_tx(tx_id, reason=''):
    with get_db() as db:
        db.execute(
            'UPDATE transactions SET status="rejected",ref=?,resolved_at=datetime("now") WHERE id=?',
            (reason, tx_id)
        )


def pending_transactions():
    with get_db() as db:
        return db.execute(
            '''SELECT t.*,u.username,u.discord_id,p.name as pkg_name,p.price_eur
               FROM transactions t
               JOIN users u ON t.user_id=u.id
               LEFT JOIN credit_packages p ON t.package_id=p.id
               WHERE t.status="pending"
               ORDER BY t.created_at DESC'''
        ).fetchall()


# ── PACKAGES ──────────────────────────────────────────────────────────────────

def get_package(pkg_id):
    with get_db() as db:
        return db.execute('SELECT * FROM credit_packages WHERE id=? AND is_active=1', (pkg_id,)).fetchone()


def all_packages():
    with get_db() as db:
        return db.execute('SELECT * FROM credit_packages WHERE is_active=1 ORDER BY sort_order').fetchall()


def upsert_package(pkg_id=None, name='', credits=0, bonus=0, price_eur=0, color='#30728C', tag=''):
    with get_db() as db:
        if pkg_id:
            db.execute(
                'UPDATE credit_packages SET name=?,credits=?,bonus=?,price_eur=?,color=?,tag=? WHERE id=?',
                (name, credits, bonus, price_eur, color, tag, pkg_id)
            )
        else:
            db.execute(
                'INSERT INTO credit_packages (name,credits,bonus,price_eur,color,tag) VALUES (?,?,?,?,?,?)',
                (name, credits, bonus, price_eur, color, tag)
            )


# ── API KEYS ──────────────────────────────────────────────────────────────────

def create_api_key(user_id, name='API Key'):
    raw = secrets.token_urlsafe(32)
    prefix = raw[:8]
    h = hashlib.sha256(raw.encode()).hexdigest()
    with get_db() as db:
        db.execute(
            'INSERT INTO api_keys (user_id,key_hash,key_prefix,name) VALUES (?,?,?,?)',
            (user_id, h, prefix, name)
        )
    return raw  # devolver solo la primera vez


def get_user_by_api_key(raw_key):
    h = hashlib.sha256(raw_key.encode()).hexdigest()
    with get_db() as db:
        row = db.execute(
            'SELECT u.* FROM api_keys k JOIN users u ON k.user_id=u.id WHERE k.key_hash=? AND k.is_active=1 AND u.is_banned=0',
            (h,)
        ).fetchone()
        if row:
            db.execute('UPDATE api_keys SET last_used=datetime("now") WHERE key_hash=?', (h,))
        return row


def list_api_keys(user_id):
    with get_db() as db:
        return db.execute(
            'SELECT id,key_prefix,name,is_active,created_at,last_used FROM api_keys WHERE user_id=? ORDER BY created_at DESC',
            (user_id,)
        ).fetchall()


def revoke_api_key(key_id, user_id):
    with get_db() as db:
        db.execute('UPDATE api_keys SET is_active=0 WHERE id=? AND user_id=?', (key_id, user_id))


# ── STATS ─────────────────────────────────────────────────────────────────────

def admin_stats():
    with get_db() as db:
        return {
            'total_users':    db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
            'total_credits':  db.execute('SELECT COALESCE(SUM(credits),0) FROM users').fetchone()[0],
            'pending_tx':     db.execute('SELECT COUNT(*) FROM transactions WHERE status="pending"').fetchone()[0],
            'completed_tx':   db.execute('SELECT COUNT(*) FROM transactions WHERE status="completed"').fetchone()[0],
            'new_today':      db.execute('SELECT COUNT(*) FROM users WHERE date(created_at)=date("now")').fetchone()[0],
        }


# ── INIT ON IMPORT ────────────────────────────────────────────────────────────
init_db()
