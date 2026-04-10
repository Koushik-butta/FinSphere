"""
Category routes — manage document categories (admin only).
"""

from flask import Blueprint, request, redirect, url_for, session, flash, jsonify
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
    icon  = request.form.get('icon', 'bi-folder').strip() or 'bi-folder'
    color = request.form.get('color', '#2563eb').strip() or '#2563eb'
    fid   = session['family_id']
    uid   = session['user_id']

    if not name:
        flash('Category name is required.', 'danger')
        return redirect(url_for('doc.dashboard') + '#categories')

    conn = get_db_connection()
    exists = conn.execute(
        'SELECT id FROM categories WHERE family_id=? AND LOWER(name)=?',
        (fid, name.lower())
    ).fetchone()
    if exists:
        conn.close()
        flash(f'Category "{name}" already exists.', 'warning')
        return redirect(url_for('doc.dashboard') + '#categories')

    conn.execute(
        'INSERT INTO categories (name, icon, color, family_id, created_by) VALUES (?,?,?,?,?)',
        (name, icon, color, fid, uid)
    )
    conn.commit()
    conn.close()
    flash(f'Category "{name}" created successfully.', 'success')
    return redirect(url_for('doc.dashboard') + '#categories')


@cat_bp.route('/categories/delete/<int:cat_id>', methods=['POST'])
@admin_required
def delete_category(cat_id):
    fid = session['family_id']
    conn = get_db_connection()
    cat = conn.execute('SELECT * FROM categories WHERE id=? AND family_id=?', (cat_id, fid)).fetchone()
    if not cat:
        conn.close()
        flash('Category not found.', 'danger')
        return redirect(url_for('doc.dashboard') + '#categories')
    # Unlink documents
    conn.execute('UPDATE documents SET category_id=NULL WHERE category_id=?', (cat_id,))
    conn.execute('DELETE FROM categories WHERE id=?', (cat_id,))
    conn.commit()
    conn.close()
    flash(f'Category "{cat["name"]}" deleted.', 'success')
    return redirect(url_for('doc.dashboard') + '#categories')
