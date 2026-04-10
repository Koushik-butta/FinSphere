from database import get_db_connection


def save_document(user_id, family_id, filename, filepath, description='',
                  category_id=None, tags='', file_size=0):
    conn = get_db_connection()
    conn.execute(
        '''INSERT INTO documents
           (uploaded_by, family_id, filename, filepath, description,
            category_id, tags, file_size)
           VALUES (?,?,?,?,?,?,?,?)''',
        (user_id, family_id, filename, filepath, description,
         category_id, tags, file_size)
    )
    conn.commit()
    conn.close()


def log_download(document_id, document_name, user_id):
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO download_history (document_id, document_name, downloaded_by) VALUES (?,?,?)',
        (document_id, document_name, user_id)
    )
    conn.commit()
    conn.close()


def get_document(doc_id):
    conn = get_db_connection()
    doc = conn.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
    conn.close()
    return doc


def delete_document(doc_id, soft=True):
    conn = get_db_connection()
    if soft:
        conn.execute('UPDATE documents SET is_deleted = 1 WHERE id=?', (doc_id,))
    else:
        conn.execute('DELETE FROM documents WHERE id=?', (doc_id,))
    conn.commit()
    conn.close()


def restore_document(doc_id):
    conn = get_db_connection()
    conn.execute('UPDATE documents SET is_deleted = 0 WHERE id=?', (doc_id,))
    conn.commit()
    conn.close()


def update_document_tags(doc_id, tags):
    conn = get_db_connection()
    conn.execute('UPDATE documents SET tags=? WHERE id=?', (tags, doc_id))
    conn.commit()
    conn.close()