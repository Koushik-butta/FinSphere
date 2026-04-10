import sqlite3
from config import DB_FILE

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()

    # Families table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS families (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_code TEXT UNIQUE,
            admin_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT,
            family_id INTEGER,
            otp TEXT,
            otp_expiry TEXT,
            reset_otp TEXT,
            reset_otp_expiry TEXT
        )
    ''')

    # Documents table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            filepath TEXT,
            description TEXT,
            uploaded_by INTEGER,
            family_id INTEGER,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        )
    ''')

    # Download History table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS download_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            document_name TEXT,
            downloaded_by INTEGER,
            download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Document Permissions table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS document_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            can_view INTEGER DEFAULT 1,
            can_download INTEGER DEFAULT 1,
            UNIQUE(document_id, user_id),
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Document Categories table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon TEXT DEFAULT 'bi-folder',
            color TEXT DEFAULT '#2563eb',
            family_id INTEGER,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Activity Log table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            family_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            icon TEXT DEFAULT 'bi-activity',
            color TEXT DEFAULT '#2563eb',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()

    # Migrate: add columns to documents if they don't exist
    migrations = [
        ('category_id', 'INTEGER DEFAULT NULL'),
        ('tags',        'TEXT DEFAULT ""'),
        ('file_size',   'INTEGER DEFAULT 0'),
    ]
    for col, defn in migrations:
        try:
            conn.execute(f'ALTER TABLE documents ADD COLUMN {col} {defn}')
            conn.commit()
        except Exception:
            pass  # Column already exists

    # Seed default categories per family (run once, idempotent)
    _seed_default_categories(conn)

    conn.close()


def _seed_default_categories(conn):
    """Insert built-in category presets for any family that has none."""
    defaults = [
        ('Bank Documents',      'bi-bank2',              '#2563eb'),
        ('Personal Documents',  'bi-person-vcard-fill',  '#7c3aed'),
        ('Insurance Documents', 'bi-shield-fill-check',  '#059669'),
        ('Education Documents', 'bi-mortarboard-fill',   '#d97706'),
        ('Other Documents',     'bi-folder-fill',        '#64748b'),
    ]
    families = conn.execute('SELECT id FROM families').fetchall()
    for fam in families:
        fid = fam['id']
        existing = conn.execute(
            'SELECT COUNT(*) as cnt FROM categories WHERE family_id=?', (fid,)
        ).fetchone()['cnt']
        if existing == 0:
            for name, icon, color in defaults:
                conn.execute(
                    'INSERT INTO categories (name, icon, color, family_id, created_by) VALUES (?,?,?,?,0)',
                    (name, icon, color, fid)
                )
    conn.commit()