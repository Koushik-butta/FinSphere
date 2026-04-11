"""
database.py — PostgreSQL backend (psycopg2 + ThreadedConnectionPool).

Uses a connection pool so workers share connections efficiently.
Auto-reconnects if the DB drops idle connections overnight (common with
Neon / Render free-tier Postgres).
"""

import logging
import psycopg2
import psycopg2.extras
import psycopg2.pool
from config import DATABASE_URL

logger = logging.getLogger(__name__)

# ── Connection pool ───────────────────────────────────────────────────────────
# minconn=1  — always keep at least 1 warm connection
# maxconn=10 — never exceed 10 simultaneous connections (Neon free limit)
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Lazily create (or re-create) the global connection pool."""
    global _pool
    if _pool is None or _pool.closed:
        logger.info("[DB] Creating connection pool…")
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return _pool


class _PooledConn:
    """
    Thin wrapper that returns the underlying connection to the pool
    when close() is called, instead of destroying it.
    All other attribute access is forwarded transparently.
    """
    def __init__(self, raw_conn, pool):
        self._conn = raw_conn
        self._pool = pool

    # Forward everything to the real connection
    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        try:
            self._pool.putconn(self._conn)
        except Exception as exc:
            logger.warning("[DB] Could not return conn to pool: %s", exc)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    @property
    def autocommit(self):
        return self._conn.autocommit

    @autocommit.setter
    def autocommit(self, value):
        self._conn.autocommit = value


# ── Public helper ─────────────────────────────────────────────────────────────

def get_db_connection() -> _PooledConn:
    """
    Borrow a connection from the pool.

    If the borrowed connection is stale (e.g. Render/Neon closed it after
    an idle night), the pool is rebuilt and a fresh connection is returned.
    Callers still just do conn.close() — the wrapper returns it to the pool.
    """
    pool = _get_pool()
    try:
        raw = pool.getconn()
        raw.autocommit = False
        # Heartbeat — detect broken connections immediately
        with raw.cursor() as cur:
            cur.execute("SELECT 1")
        return _PooledConn(raw, pool)
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
        logger.warning("[DB] Stale connection detected (%s) — rebuilding pool…", exc)
        # Recreate the pool on the next call
        global _pool
        try:
            _pool.closeall()
        except Exception:
            pass
        _pool = None
        # Retry once with a fresh pool
        pool = _get_pool()
        raw  = pool.getconn()
        raw.autocommit = False
        return _PooledConn(raw, pool)


# ── Schema Init ───────────────────────────────────────────────────────────────

def init_db():
    conn = get_db_connection()
    cur  = conn.cursor()

    # ── Families ──────────────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS families (
            id          SERIAL PRIMARY KEY,
            family_code TEXT UNIQUE,
            admin_id    INTEGER,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Users ─────────────────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id                 SERIAL PRIMARY KEY,
            name               TEXT,
            email              TEXT UNIQUE,
            password           TEXT,
            role               TEXT,
            family_id          INTEGER,
            otp                TEXT,
            otp_expiry         TEXT,
            reset_otp          TEXT,
            reset_otp_expiry   TEXT
        )
    ''')

    # ── Documents ─────────────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id          SERIAL PRIMARY KEY,
            filename    TEXT,
            filepath    TEXT,
            description TEXT,
            uploaded_by INTEGER,
            family_id   INTEGER,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted  INTEGER   DEFAULT 0,
            category_id INTEGER   DEFAULT NULL,
            tags        TEXT      DEFAULT '',
            file_size   INTEGER   DEFAULT 0,
            expiry_date DATE      DEFAULT NULL,
            is_emergency BOOLEAN  DEFAULT FALSE
        )
    ''')

    # ── Download History ──────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS download_history (
            id            SERIAL PRIMARY KEY,
            document_id   INTEGER,
            document_name TEXT,
            downloaded_by INTEGER,
            download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Document Permissions ──────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS document_permissions (
            id          SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            can_view    INTEGER DEFAULT 1,
            can_download INTEGER DEFAULT 1,
            UNIQUE(document_id, user_id),
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (user_id)     REFERENCES users(id)
        )
    ''')

    # ── Categories ────────────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id         SERIAL PRIMARY KEY,
            name       TEXT NOT NULL,
            icon       TEXT DEFAULT 'bi-folder',
            color      TEXT DEFAULT '#2563eb',
            family_id  INTEGER,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Activity Log ──────────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER,
            family_id  INTEGER,
            action     TEXT NOT NULL,
            details    TEXT,
            icon       TEXT DEFAULT 'bi-activity',
            color      TEXT DEFAULT '#2563eb',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Login Attempts (rate-limit audit) ─────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id           SERIAL PRIMARY KEY,
            email        TEXT,
            ip_address   TEXT,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()

    # ── Safe column migrations (idempotent) ───────────────────────────────────
    _safe_add_column(cur, conn, 'documents', 'expiry_date',  'DATE DEFAULT NULL')
    _safe_add_column(cur, conn, 'documents', 'is_emergency', 'BOOLEAN DEFAULT FALSE')
    _safe_add_column(cur, conn, 'documents', 'category_id',  'INTEGER DEFAULT NULL')
    _safe_add_column(cur, conn, 'documents', 'tags',         "TEXT DEFAULT ''")
    _safe_add_column(cur, conn, 'documents', 'file_size',    'INTEGER DEFAULT 0')

    # ── Seed default categories ───────────────────────────────────────────────
    _seed_default_categories(cur, conn)

    conn.commit()
    cur.close()
    conn.close()


def _safe_add_column(cur, conn, table, column, definition):
    """Add a column to a table if it does not already exist (idempotent)."""
    try:
        cur.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}')
        conn.commit()
    except Exception:
        conn.rollback()


def _seed_default_categories(cur, conn):
    """Insert built-in category presets for any family that has none."""
    defaults = [
        ('Bank Documents',      'bi-bank2',              '#2563eb'),
        ('Personal Documents',  'bi-person-vcard-fill',  '#7c3aed'),
        ('Insurance Documents', 'bi-shield-fill-check',  '#059669'),
        ('Education Documents', 'bi-mortarboard-fill',   '#d97706'),
        ('Other Documents',     'bi-folder-fill',        '#64748b'),
    ]
    cur.execute('SELECT id FROM families')
    families = cur.fetchall()
    for fam in families:
        fid = fam['id']
        cur.execute('SELECT COUNT(*) AS cnt FROM categories WHERE family_id=%s', (fid,))
        if cur.fetchone()['cnt'] == 0:
            for name, icon, color in defaults:
                cur.execute(
                    'INSERT INTO categories (name, icon, color, family_id, created_by) VALUES (%s,%s,%s,%s,0)',
                    (name, icon, color, fid)
                )
    conn.commit()