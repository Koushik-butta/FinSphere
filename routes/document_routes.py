from flask import Blueprint, render_template, request, redirect, session, url_for, send_from_directory, flash, jsonify
from services.document_service import save_document, get_document, delete_document, restore_document, log_download
from services.permission_service import (
    get_family_members, can_user_view, can_user_download,
    get_all_permissions_for_family, bulk_set_permissions
)
from services.activity_service import (
    log_activity, get_recent_activity, get_analytics, get_storage_info
)
from config import UPLOAD_FOLDER
import os
from database import get_db_connection
from werkzeug.utils import secure_filename
from datetime import datetime

doc_bp = Blueprint('doc', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Access denied. Admins only.', 'danger')
            return redirect(url_for('doc.dashboard'))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────────

@doc_bp.route('/dashboard')
@login_required
def dashboard():
    family_id = session.get('family_id')
    user_id   = session.get('user_id')
    role      = session.get('role')

    conn = get_db_connection()

    # Family code (everyone)
    family_code = None
    fam = conn.execute("SELECT family_code FROM families WHERE id=?", (family_id,)).fetchone()
    if fam:
        family_code = fam['family_code']

    # Active documents with category info
    all_docs = conn.execute('''
        SELECT d.id, d.filename, d.description, d.upload_date,
               d.tags, d.file_size, d.category_id,
               u.name AS user_name,
               c.name AS category_name, c.icon AS category_icon, c.color AS category_color
        FROM documents d
        JOIN users u ON d.uploaded_by = u.id
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE d.family_id = ? AND d.is_deleted = 0
        ORDER BY d.upload_date DESC
    ''', (family_id,)).fetchall()

    if role == 'member':
        documents = [doc for doc in all_docs if can_user_view(doc['id'], user_id, role)]
    else:
        documents = all_docs

    # Admin-only data
    download_history   = []
    deleted_documents  = []
    all_permissions    = {}
    categories         = []
    activity           = []
    storage            = {}
    analytics          = {}
    member_count       = 0
    
    # Family members (everyone)
    family_members = conn.execute(
        "SELECT id, name, email, role FROM users WHERE family_id=?", (family_id,)
    ).fetchall()

    # Member count for everyone
    member_count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM users WHERE family_id=?", (family_id,)
    ).fetchone()['cnt']

    # Categories (everyone)
    categories = conn.execute(
        "SELECT * FROM categories WHERE family_id=? ORDER BY name", (family_id,)
    ).fetchall()

    if role == 'admin':
        download_history = conn.execute('''
            SELECT dh.document_name, dh.download_time, u.name AS downloaded_by
            FROM download_history dh
            JOIN users u ON dh.downloaded_by = u.id
            WHERE u.family_id = ?
            ORDER BY dh.download_time DESC
        ''', (family_id,)).fetchall()

        deleted_documents = conn.execute('''
            SELECT d.id, d.filename, d.upload_date, u.name AS user_name
            FROM documents d
            JOIN users u ON d.uploaded_by = u.id
            WHERE d.family_id = ? AND d.is_deleted = 1
            ORDER BY d.upload_date DESC
        ''', (family_id,)).fetchall()

        all_permissions = get_all_permissions_for_family(family_id)
        activity  = get_recent_activity(family_id, limit=15)
        storage   = get_storage_info(family_id)
        analytics = get_analytics(family_id)

    conn.close()

    return render_template(
        'dashboard.html',
        documents=documents,
        role=role,
        name=session.get('name'),
        family_code=family_code,
        download_history=download_history,
        deleted_documents=deleted_documents,
        family_members=family_members,
        all_permissions=all_permissions,
        categories=categories,
        activity=activity,
        storage=storage,
        analytics=analytics,
        member_count=member_count,
    )


# ── Upload ────────────────────────────────────────────────────────────────────

@doc_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
def upload():
    family_id = session['family_id']
    conn = get_db_connection()
    categories = conn.execute(
        "SELECT * FROM categories WHERE family_id=? ORDER BY name", (family_id,)
    ).fetchall()
    conn.close()

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file detected in upload.', 'danger')
            return redirect(request.url)

        file        = request.files['file']
        user_id     = session['user_id']
        description = request.form.get('description', '')
        category_id = request.form.get('category_id') or None
        tags        = request.form.get('tags', '').strip()

        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Invalid file type. Only PDF, JPG, and PNG files are allowed.', 'danger')
            return redirect(request.url)

        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_filename = f"{timestamp}_{original_filename}"

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        try:
            file.save(filepath)
            file_size = os.path.getsize(filepath)
            save_document(user_id, family_id, original_filename, filepath,
                          description, category_id, tags, file_size)
            log_activity(user_id, family_id, 'upload',
                         f'{session["name"]} uploaded {original_filename}')
            flash(f'Document "{original_filename}" uploaded successfully!', 'success')
            return redirect(url_for('doc.dashboard'))
        except Exception as e:
            flash(f'An error occurred while uploading: {str(e)}', 'danger')

    return render_template('upload.html', name=session['name'], categories=categories)


# ── Preview (inline) ──────────────────────────────────────────────────────────

@doc_bp.route('/preview/<int:doc_id>')
@login_required
def preview(doc_id):
    user_id = session['user_id']
    role    = session['role']

    doc = get_document(doc_id)
    if not doc or doc['family_id'] != session['family_id'] or doc['is_deleted']:
        return 'Document not found', 404

    if not can_user_view(doc_id, user_id, role):
        return 'Access denied', 403

    try:
        if doc['filepath'].startswith('http'):
            return redirect(doc['filepath'])

        directory = os.path.abspath(UPLOAD_FOLDER)
        filename_on_disk = os.path.basename(doc['filepath'])
        ext = filename_on_disk.rsplit('.', 1)[-1].lower()
        mime_map = {'pdf': 'application/pdf', 'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg', 'png': 'image/png'}
        mimetype = mime_map.get(ext, 'application/octet-stream')
        return send_from_directory(directory, filename_on_disk,
                                   as_attachment=False, mimetype=mimetype)
    except Exception:
        return 'File not found', 404


# ── Download ──────────────────────────────────────────────────────────────────

@doc_bp.route('/download/<int:doc_id>')
@login_required
def download(doc_id):
    user_id = session['user_id']
    role    = session['role']

    doc = get_document(doc_id)
    if not doc or doc['family_id'] != session['family_id'] or doc['is_deleted']:
        flash('Document not found.', 'danger')
        return redirect(url_for('doc.dashboard'))

    if not can_user_download(doc_id, user_id, role):
        flash('You do not have permission to download this document.', 'danger')
        return redirect(url_for('doc.dashboard'))

    try:
        log_download(doc['id'], doc['filename'], user_id)
        log_activity(user_id, session['family_id'], 'download',
                     f'{session["name"]} downloaded {doc["filename"]}')

        if doc['filepath'].startswith('http'):
            import urllib.request
            import io
            from flask import send_file
            req = urllib.request.Request(doc['filepath'], headers={'User-Agent': 'Mozilla/5.0'})
            try:
                with urllib.request.urlopen(req) as response:
                    file_data = response.read()
                return send_file(
                    io.BytesIO(file_data),
                    as_attachment=True,
                    download_name=doc['filename'],
                    mimetype=response.headers.get('Content-Type', 'application/octet-stream')
                )
            except Exception as e:
                flash('Error fetching remote file.', 'danger')
                return redirect(url_for('doc.dashboard'))

        directory = os.path.abspath(UPLOAD_FOLDER)
        filename_on_disk = os.path.basename(doc['filepath'])
        return send_from_directory(directory, filename_on_disk,
                                   as_attachment=True, download_name=doc['filename'])
    except Exception:
        flash('Error fetching file.', 'danger')
        return redirect(url_for('doc.dashboard'))


# ── Delete / Restore / Hard Delete ────────────────────────────────────────────

@doc_bp.route('/delete/<int:doc_id>', methods=['POST'])
@admin_required
def delete(doc_id):
    doc = get_document(doc_id)
    if not doc or doc['family_id'] != session['family_id']:
        flash('Document not found.', 'danger')
        return redirect(url_for('doc.dashboard'))
    delete_document(doc_id, soft=True)
    log_activity(session['user_id'], session['family_id'], 'delete',
                 f'{session["name"]} deleted {doc["filename"]}')
    flash('Document moved to Recycle Bin.', 'success')
    return redirect(url_for('doc.dashboard'))


@doc_bp.route('/admin/restore/<int:doc_id>', methods=['POST'])
@admin_required
def restore(doc_id):
    doc = get_document(doc_id)
    if not doc or doc['family_id'] != session['family_id']:
        flash('Document not found.', 'danger')
        return redirect(url_for('doc.dashboard'))
    restore_document(doc_id)
    log_activity(session['user_id'], session['family_id'], 'restore',
                 f'{session["name"]} restored {doc["filename"]}')
    flash('Document restored successfully.', 'success')
    return redirect(url_for('doc.dashboard') + '#recycle')


@doc_bp.route('/admin/hard-delete/<int:doc_id>', methods=['POST'])
@admin_required
def hard_delete(doc_id):
    doc = get_document(doc_id)
    if not doc or doc['family_id'] != session['family_id']:
        flash('Document not found.', 'danger')
        return redirect(url_for('doc.dashboard'))
    try:
        # Only remove file from disk if it's a local path (not Cloudinary)
        if doc['filepath'] and not doc['filepath'].startswith('http'):
            if os.path.exists(doc['filepath']):
                os.remove(doc['filepath'])
        delete_document(doc_id, soft=False)
        flash('Document permanently deleted.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('doc.dashboard') + '#recycle')


# ── Permissions ───────────────────────────────────────────────────────────────

@doc_bp.route('/admin/permissions/<int:doc_id>', methods=['POST'])
@admin_required
def update_permissions(doc_id):
    doc = get_document(doc_id)
    if not doc or doc['family_id'] != session['family_id']:
        flash('Document not found.', 'danger')
        return redirect(url_for('doc.dashboard'))

    family_id = session['family_id']
    user_id   = session['user_id']
    members   = get_family_members(family_id, exclude_user_id=user_id)

    perms = {}
    for m in members:
        mid = m['id']
        perms[mid] = {
            'can_view':     1 if request.form.get(f'view_{mid}')     else 0,
            'can_download': 1 if request.form.get(f'download_{mid}') else 0,
        }
    bulk_set_permissions(doc_id, perms)
    log_activity(user_id, family_id, 'permission',
                 f'Admin updated permissions for {doc["filename"]}')
    flash(f'Permissions updated for "{doc["filename"]}".', 'success')
    return redirect(url_for('doc.dashboard') + '#permissions')


# ── API: Search ───────────────────────────────────────────────────────────────

@doc_bp.route('/api/search')
@login_required
def api_search():
    q         = request.args.get('q', '').strip().lower()
    family_id = session['family_id']
    user_id   = session['user_id']
    role      = session['role']

    if not q:
        return jsonify([])

    conn = get_db_connection()
    rows = conn.execute('''
        SELECT d.id, d.filename, d.description, d.tags, u.name AS user_name
        FROM documents d
        JOIN users u ON d.uploaded_by = u.id
        WHERE d.family_id=? AND d.is_deleted=0
          AND (LOWER(d.filename) LIKE ? OR LOWER(d.description) LIKE ? OR LOWER(d.tags) LIKE ?)
        ORDER BY d.upload_date DESC LIMIT 10
    ''', (family_id, f'%{q}%', f'%{q}%', f'%{q}%')).fetchall()
    conn.close()

    results = []
    for r in rows:
        if role == 'admin' or can_user_view(r['id'], user_id, role):
            results.append({
                'id': r['id'], 'filename': r['filename'],
                'description': r['description'], 'user_name': r['user_name'],
                'tags': r['tags'],
            })
    return jsonify(results)


# ── API: Analytics ────────────────────────────────────────────────────────────

@doc_bp.route('/api/analytics')
@admin_required
def api_analytics():
    return jsonify(get_analytics(session['family_id']))