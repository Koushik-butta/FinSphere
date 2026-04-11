"""
Permission service — manages per-document, per-user access control.
Uses psycopg2 (%s placeholders).
"""

from database import get_db_connection


def get_family_members(family_id, exclude_user_id=None):
    """Return all members of a family (optionally excluding one user)."""
    conn = get_db_connection()
    cur  = conn.cursor()
    if exclude_user_id:
        cur.execute(
            "SELECT id, name, email, role FROM users WHERE family_id=%s AND id!=%s",
            (family_id, exclude_user_id)
        )
    else:
        cur.execute(
            "SELECT id, name, email, role FROM users WHERE family_id=%s",
            (family_id,)
        )
    members = cur.fetchall()
    cur.close()
    conn.close()
    return members


def get_document_permissions(doc_id):
    """Return all permission rows for a document, keyed by user_id."""
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM document_permissions WHERE document_id=%s", (doc_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row['user_id']: row for row in rows}


def set_permission(doc_id, user_id, can_view, can_download):
    """Insert or update a permission row for a specific user/document pair."""
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute('''
        INSERT INTO document_permissions (document_id, user_id, can_view, can_download)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (document_id, user_id)
        DO UPDATE SET can_view=EXCLUDED.can_view, can_download=EXCLUDED.can_download
    ''', (doc_id, user_id, int(can_view), int(can_download)))
    conn.commit()
    cur.close()
    conn.close()


def can_user_view(doc_id, user_id, role):
    """
    Check if a user can view a document.
    Admins can always view. Members need explicit can_view=1.
    If no permission record exists, default is allowed (open by default).
    """
    if role == 'admin':
        return True
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT can_view FROM document_permissions WHERE document_id=%s AND user_id=%s",
        (doc_id, user_id)
    )
    perm = cur.fetchone()
    cur.close()
    conn.close()
    if perm is None:
        return True  # Default: open access
    return bool(perm['can_view'])


def can_user_download(doc_id, user_id, role):
    """
    Check if a user can download a document.
    Admins can always download. Members need explicit can_download=1.
    If no permission record exists, default is allowed.
    """
    if role == 'admin':
        return True
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT can_download FROM document_permissions WHERE document_id=%s AND user_id=%s",
        (doc_id, user_id)
    )
    perm = cur.fetchone()
    cur.close()
    conn.close()
    if perm is None:
        return True  # Default: open access
    return bool(perm['can_download'])


def bulk_set_permissions(doc_id, permissions_dict):
    """
    Set permissions for multiple users at once.
    permissions_dict: { user_id: {'can_view': bool, 'can_download': bool} }
    """
    conn = get_db_connection()
    cur  = conn.cursor()
    for user_id, perms in permissions_dict.items():
        cur.execute('''
            INSERT INTO document_permissions (document_id, user_id, can_view, can_download)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (document_id, user_id)
            DO UPDATE SET can_view=EXCLUDED.can_view, can_download=EXCLUDED.can_download
        ''', (doc_id, user_id, int(perms.get('can_view', 1)), int(perms.get('can_download', 1))))
    conn.commit()
    cur.close()
    conn.close()


def get_all_permissions_for_family(family_id):
    """
    Return a nested dict: { doc_id: { user_id: {can_view, can_download} } }
    for quick lookup in the dashboard.
    """
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT dp.document_id, dp.user_id, dp.can_view, dp.can_download
        FROM document_permissions dp
        JOIN documents d ON dp.document_id = d.id
        WHERE d.family_id = %s
    ''', (family_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = {}
    for row in rows:
        doc_id  = row['document_id']
        user_id = row['user_id']
        if doc_id not in result:
            result[doc_id] = {}
        result[doc_id][user_id] = {
            'can_view':     bool(row['can_view']),
            'can_download': bool(row['can_download']),
        }
    return result
