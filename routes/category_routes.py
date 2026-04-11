"""
Category routes — manage document categories (admin only).
Uses psycopg2 (%s placeholders).
"""

from flask import Blueprint, request, redirect, url_for, session, flash
from database import get_db_connection

cat_bp = Blueprint('cat', __name__)


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Admins only.', 'danger')
            return redirect(url_for('doc.dashboard'))
        return f(*args, **kwargs)
    return decorated


@cat_bp.route('/categories/create', methods=['POST'])
@admin_required
def create_category():
    name  = request.form.get('name', '').strip()
    icon  = request.form.get('icon',  'bi-folder').strip() or 'bi-folder'
    color = request.form.get('color', '#2563eb').strip() or '#2563eb'
    fid   = session['family_id']
    uid   = session['user_id']

    if not name:
        flash('Category name is required.', 'danger')
        return redirect(url_for('doc.dashboard') + '#categories')

    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute(
        'SELECT id FROM categories WHERE family_id=%s AND LOWER(name)=%s',
        (fid, name.lower())
    )
    if cur.fetchone():
        cur.close(); conn.close()
        flash(f'Category "{name}" already exists.', 'warning')
        return redirect(url_for('doc.dashboard') + '#categories')

    cur.execute(
        'INSERT INTO categories (name, icon, color, family_id, created_by) VALUES (%s,%s,%s,%s,%s)',
        (name, icon, color, fid, uid)
    )
    conn.commit()
    cur.close()
    conn.close()
    flash(f'Category "{name}" created successfully.', 'success')
    return redirect(url_for('doc.dashboard') + '#categories')


@cat_bp.route('/categories/delete/<int:cat_id>', methods=['POST'])
@admin_required
def delete_category(cat_id):
    fid  = session['family_id']
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute('SELECT * FROM categories WHERE id=%s AND family_id=%s', (cat_id, fid))
    cat = cur.fetchone()
    if not cat:
        cur.close(); conn.close()
        flash('Category not found.', 'danger')
        return redirect(url_for('doc.dashboard') + '#categories')

    # Unlink documents
    cur.execute('UPDATE documents SET category_id=NULL WHERE category_id=%s', (cat_id,))
    cur.execute('DELETE FROM categories WHERE id=%s', (cat_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash(f'Category "{cat["name"]}" deleted.', 'success')
    return redirect(url_for('doc.dashboard') + '#categories')
