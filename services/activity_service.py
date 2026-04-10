"""
Activity log service — records all user actions for the family timeline.
"""

from database import get_db_connection


# ── Action constants ──────────────────────────────────────────────────────────
ICONS = {
    'upload':     ('bi-cloud-upload-fill',      '#10b981'),
    'download':   ('bi-cloud-arrow-down-fill',  '#2563eb'),
    'delete':     ('bi-trash3-fill',            '#ef4444'),
    'restore':    ('bi-arrow-counterclockwise', '#f59e0b'),
    'permission': ('bi-person-lock-fill',       '#7c3aed'),
    'login':      ('bi-box-arrow-in-right',     '#14b8a6'),
    'register':   ('bi-person-plus-fill',       '#10b981'),
    'category':   ('bi-folder-plus-fill',       '#f97316'),
}


def log_activity(user_id: int, family_id: int, action_type: str, details: str) -> None:
    """Insert a new activity log entry."""
    icon, color = ICONS.get(action_type, ('bi-activity', '#64748b'))
    try:
        conn = get_db_connection()
        conn.execute(
            '''INSERT INTO activity_log (user_id, family_id, action, details, icon, color)
               VALUES (?,?,?,?,?,?)''',
            (user_id, family_id, action_type, details, icon, color)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ACTIVITY] Log error: {e}")


def get_recent_activity(family_id: int, limit: int = 20) -> list:
    """Return recent activity entries for a family."""
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT al.action, al.details, al.icon, al.color, al.created_at,
               u.name AS user_name
        FROM activity_log al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE al.family_id = ?
        ORDER BY al.created_at DESC
        LIMIT ?
    ''', (family_id, limit)).fetchall()
    conn.close()
    return rows


def get_analytics(family_id: int) -> dict:
    """Return analytics data: uploads/downloads per day for last 7 days."""
    from datetime import date, timedelta

    conn = get_db_connection()

    # Last 7 days labels
    today = date.today()
    days  = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    labels = [(today - timedelta(days=i)).strftime('%b %d') for i in range(6, -1, -1)]

    # Uploads per day
    up_rows = conn.execute('''
        SELECT date(upload_date) AS day, COUNT(*) AS cnt
        FROM documents
        WHERE family_id=? AND upload_date >= date('now', '-7 days') AND is_deleted=0
        GROUP BY date(upload_date)
    ''', (family_id,)).fetchall()
    up_map = {r['day']: r['cnt'] for r in up_rows}

    # Downloads per day
    dl_rows = conn.execute('''
        SELECT date(dh.download_time) AS day, COUNT(*) AS cnt
        FROM download_history dh
        JOIN users u ON dh.downloaded_by = u.id
        WHERE u.family_id=? AND dh.download_time >= date('now', '-7 days')
        GROUP BY date(dh.download_time)
    ''', (family_id,)).fetchall()
    dl_map = {r['day']: r['cnt'] for r in dl_rows}

    # Most-accessed document
    top_doc = conn.execute('''
        SELECT d.filename, COUNT(dh.id) AS cnt
        FROM download_history dh
        JOIN documents d ON dh.document_id = d.id
        WHERE d.family_id=?
        GROUP BY dh.document_id
        ORDER BY cnt DESC LIMIT 1
    ''', (family_id,)).fetchone()

    # Most-active member
    top_member = conn.execute('''
        SELECT u.name, COUNT(dh.id) AS cnt
        FROM download_history dh
        JOIN users u ON dh.downloaded_by = u.id
        WHERE u.family_id=?
        GROUP BY dh.downloaded_by
        ORDER BY cnt DESC LIMIT 1
    ''', (family_id,)).fetchone()

    # Uploads today
    up_today = conn.execute('''
        SELECT COUNT(*) AS cnt FROM documents
        WHERE family_id=? AND date(upload_date)=date('now') AND is_deleted=0
    ''', (family_id,)).fetchone()['cnt']

    # Downloads today
    dl_today = conn.execute('''
        SELECT COUNT(*) AS cnt FROM download_history dh
        JOIN users u ON dh.downloaded_by = u.id
        WHERE u.family_id=? AND date(dh.download_time)=date('now')
    ''', (family_id,)).fetchone()['cnt']

    conn.close()

    return {
        'labels':     labels,
        'uploads':    [up_map.get(d, 0) for d in days],
        'downloads':  [dl_map.get(d, 0) for d in days],
        'top_doc':    dict(top_doc) if top_doc else None,
        'top_member': dict(top_member) if top_member else None,
        'up_today':   up_today,
        'dl_today':   dl_today,
    }


def get_storage_info(family_id: int) -> dict:
    """Return storage used (bytes) and cap for a family."""
    conn = get_db_connection()
    result = conn.execute(
        'SELECT COALESCE(SUM(file_size), 0) AS total FROM documents WHERE family_id=? AND is_deleted=0',
        (family_id,)
    ).fetchone()
    conn.close()
    used_bytes = result['total']
    cap_bytes  = 1 * 1024 * 1024 * 1024  # 1 GB cap
    pct        = round((used_bytes / cap_bytes) * 100, 1) if cap_bytes else 0

    def fmt(b):
        if b < 1024:        return f'{b} B'
        if b < 1048576:     return f'{b/1024:.1f} KB'
        if b < 1073741824:  return f'{b/1048576:.1f} MB'
        return f'{b/1073741824:.2f} GB'

    return {
        'used_bytes': used_bytes,
        'cap_bytes':  cap_bytes,
        'used_fmt':   fmt(used_bytes),
        'cap_fmt':    fmt(cap_bytes),
        'pct':        pct,
    }
