"""
Document model helpers — thin wrappers around common document queries.
Uses psycopg2 (%s placeholders).
"""

from database import get_db_connection


def get_active_documents(family_id):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT d.id, d.filename, d.description, d.upload_date, u.name AS user_name
        FROM documents d
        JOIN users u ON d.uploaded_by = u.id
        WHERE d.family_id = %s AND d.is_deleted = 0
        ORDER BY d.upload_date DESC
    ''', (family_id,))
    docs = cur.fetchall()
    cur.close()
    conn.close()
    return docs


def get_deleted_documents(family_id):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT d.id, d.filename, d.upload_date, u.name AS user_name
        FROM documents d
        JOIN users u ON d.uploaded_by = u.id
        WHERE d.family_id = %s AND d.is_deleted = 1
        ORDER BY d.upload_date DESC
    ''', (family_id,))
    docs = cur.fetchall()
    cur.close()
    conn.close()
    return docs


def get_download_history(family_id):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT dh.document_name, dh.download_time, u.name AS downloaded_by
        FROM download_history dh
        JOIN users u ON dh.downloaded_by = u.id
        WHERE u.family_id = %s
        ORDER BY dh.download_time DESC
    ''', (family_id,))
    history = cur.fetchall()
    cur.close()
    conn.close()
    return history
