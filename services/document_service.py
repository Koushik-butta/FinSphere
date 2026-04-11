"""
Document service — thin wrappers around document CRUD.
Uses psycopg2 (%s placeholders).
"""

from database import get_db_connection


def save_document(user_id, family_id, filename, filepath, description='',
                  category_id=None, tags='', file_size=0,
                  expiry_date=None, is_emergency=False):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute(
        '''INSERT INTO documents
           (uploaded_by, family_id, filename, filepath, description,
            category_id, tags, file_size, expiry_date, is_emergency)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (user_id, family_id, filename, filepath, description,
         category_id, tags, file_size, expiry_date or None, bool(is_emergency))
    )
    conn.commit()
    cur.close()
    conn.close()


def log_download(document_id, document_name, user_id):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute(
        'INSERT INTO download_history (document_id, document_name, downloaded_by) VALUES (%s,%s,%s)',
        (document_id, document_name, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_document(doc_id):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute('SELECT * FROM documents WHERE id=%s', (doc_id,))
    doc = cur.fetchone()
    cur.close()
    conn.close()
    return doc


def delete_document(doc_id, soft=True):
    conn = get_db_connection()
    cur  = conn.cursor()
    if soft:
        cur.execute('UPDATE documents SET is_deleted=1 WHERE id=%s', (doc_id,))
    else:
        cur.execute('DELETE FROM documents WHERE id=%s', (doc_id,))
    conn.commit()
    cur.close()
    conn.close()


def restore_document(doc_id):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute('UPDATE documents SET is_deleted=0 WHERE id=%s', (doc_id,))
    conn.commit()
    cur.close()
    conn.close()


def update_document_tags(doc_id, tags):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute('UPDATE documents SET tags=%s WHERE id=%s', (tags, doc_id))
    conn.commit()
    cur.close()
    conn.close()