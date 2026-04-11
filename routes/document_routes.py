"""
Document routes — upload, preview, download, delete/restore, permissions, search, analytics.
Uses psycopg2 (%s placeholders). Cloudinary-first storage (no local filesystem).
"""

import logging
from flask import (Blueprint, render_template, request, redirect, session,
                   url_for, flash, jsonify)
from services.document_service import (save_document, get_document,
                                       delete_document, restore_document, log_download)
from services.permission_service import (
    get_family_members, can_user_view, can_user_download,
    get_all_permissions_for_family, bulk_set_permissions
)
from services.activity_service import (
    log_activity, get_recent_activity, get_analytics, get_storage_info
)
from database import get_db_connection
from werkzeug.utils import secure_filename
from datetime import datetime, date
import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)

doc_bp = Blueprint('doc', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
MAX_EXPIRY_ALERT_DAYS = 30   # warn if doc expires within 30 days


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _days_until(expiry_date):
    """Return integer days until expiry_date (a date object), or None."""
    if not expiry_date:
        return None
    if isinstance(expiry_date, datetime):
        expiry_date = expiry_date.date()
    return (expiry_date - date.today()).days


# ── Dashboard ─────────────────────────────────────────────────────────────────

@doc_bp.route('/dashboard')
@login_required
def dashboard():
    family_id = session.get('family_id')
    user_id   = session.get('user_id')
    role      = session.get('role')

    conn = get_db_connection()
    cur  = conn.cursor()

    # ── Family code (ALL users) ───────────────────────────────────────────────
    family_code = None
    cur.execute("SELECT family_code FROM families WHERE id=%s", (family_id,))
    fam = cur.fetchone()
    if fam:
        family_code = fam['family_code']
    # Admin fallback: look up by admin_id if family_id somehow not set
    if not family_code and role == 'admin':
        cur.execute("SELECT family_code FROM families WHERE admin_id=%s", (user_id,))
        fam = cur.fetchone()
        if fam:
            family_code = fam['family_code']

    # ── Active documents with category info ───────────────────────────────────
    cur.execute('''
        SELECT d.id, d.filename, d.description, d.upload_date,
               d.tags, d.file_size, d.category_id,
               d.expiry_date, d.is_emergency,
               u.name AS user_name,
               c.name  AS category_name,
               c.icon  AS category_icon,
               c.color AS category_color
        FROM documents d
        JOIN users u ON d.uploaded_by = u.id
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE d.family_id = %s AND d.is_deleted = 0
        ORDER BY d.upload_date DESC
    ''', (family_id,))
    all_docs = cur.fetchall()

    if role == 'member':
        documents = [doc for doc in all_docs if can_user_view(doc['id'], user_id, role)]
    else:
        documents = all_docs

    # ── Expiry alerts ─────────────────────────────────────────────────────────
    expiry_alerts = []
    for doc in documents:
        days = _days_until(doc['expiry_date'])
        if days is not None and 0 <= days <= MAX_EXPIRY_ALERT_DAYS:
            expiry_alerts.append({
                'id':       doc['id'],
                'filename': doc['filename'],
                'days':     days,
                'urgent':   days <= 7,
            })
    expiry_alerts.sort(key=lambda x: x['days'])

    # ── Emergency documents ───────────────────────────────────────────────────
    emergency_docs = [d for d in documents if d.get('is_emergency')]

    # ── Member count ─────────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE family_id=%s", (family_id,))
    member_count = cur.fetchone()['cnt']

    # ── Categories ───────────────────────────────────────────────────────────
    cur.execute("SELECT * FROM categories WHERE family_id=%s ORDER BY name", (family_id,))
    categories = cur.fetchall()

    # ── Admin-only data ───────────────────────────────────────────────────────
    download_history  = []
    deleted_documents = []
    family_members    = []
    all_permissions   = {}
    activity          = []
    storage           = {}
    analytics         = {}

    if role == 'admin':
        cur.execute('''
            SELECT dh.document_name, dh.download_time, u.name AS downloaded_by
            FROM download_history dh
            JOIN users u ON dh.downloaded_by = u.id
            WHERE u.family_id = %s
            ORDER BY dh.download_time DESC
        ''', (family_id,))
        download_history = cur.fetchall()

        cur.execute('''
            SELECT d.id, d.filename, d.upload_date, u.name AS user_name
            FROM documents d
            JOIN users u ON d.uploaded_by = u.id
            WHERE d.family_id = %s AND d.is_deleted = 1
            ORDER BY d.upload_date DESC
        ''', (family_id,))
        deleted_documents = cur.fetchall()

        cur.execute("SELECT id, name, email, role FROM users WHERE family_id=%s", (family_id,))
        family_members = cur.fetchall()

        all_permissions = get_all_permissions_for_family(family_id)
        activity  = get_recent_activity(family_id, limit=15)
        storage   = get_storage_info(family_id)
        analytics = get_analytics(family_id)

    # ── Family members (ALL users) ────────────────────────────────────────────
    cur.execute("SELECT id, name, email, role FROM users WHERE family_id=%s", (family_id,))
    family_members = cur.fetchall()

    cur.close()
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
        expiry_alerts=expiry_alerts,
        emergency_docs=emergency_docs,
    )


# ── Upload ────────────────────────────────────────────────────────────────────

@doc_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
def upload():
    family_id = session['family_id']
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM categories WHERE family_id=%s ORDER BY name", (family_id,))
    categories = cur.fetchall()
    cur.close()
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

        # Expiry date & emergency flag
        expiry_date_str = request.form.get('expiry_date', '').strip()
        expiry_date     = None
        if expiry_date_str:
            try:
                expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
            except ValueError:
                expiry_date = None
        is_emergency = bool(request.form.get('is_emergency'))

        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Invalid file type. Only PDF, JPG, and PNG files are allowed.', 'danger')
            return redirect(request.url)

        original_filename = secure_filename(file.filename)
        
        try:
            # Upload directly to Cloudinary
            upload_result = cloudinary.uploader.upload(
                file,
                resource_type="auto",
                use_filename=True,
                unique_filename=True
            )

            secure_url = upload_result.get("secure_url")
            file_size  = upload_result.get("bytes", 0)

            save_document(
                user_id, family_id, original_filename, secure_url,
                description, category_id, tags, file_size,
                expiry_date, is_emergency
            )
            log_activity(user_id, family_id, 'upload',
                         f'{session["name"]} uploaded {original_filename}')
            logger.info(
                "[UPLOAD] user=%s family=%s file=%s size=%s url=%s",
                user_id, family_id, original_filename, file_size, secure_url
            )
            flash(f'Document "{original_filename}" uploaded successfully to Cloudinary!', 'success')
            return redirect(url_for('doc.dashboard'))
        except Exception as e:
            logger.error("[UPLOAD] Cloudinary upload failed: %s", e)
            flash(f'An error occurred while uploading to Cloudinary: {str(e)}', 'danger')

    return render_template('upload.html', name=session['name'], categories=categories)


# ── Preview (open in new tab via Cloudinary) ──────────────────────────────────

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

    # All documents are now stored on Cloudinary — redirect directly.
    filepath = doc.get('filepath', '')
    if filepath and filepath.startswith('http'):
        logger.info("[PREVIEW] user=%s doc=%s", user_id, doc_id)
        return redirect(filepath)

    # Fallback for any very old record with no Cloudinary URL
    return 'File not available. Please re-upload this document.', 410


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
        logger.info(
            "[DOWNLOAD] user=%s doc=%s file=%s",
            user_id, doc_id, doc['filename']
        )

        # Proxy download through Flask so browser triggers Save dialog
        # (Direct Cloudinary redirect opens file in browser for PDFs/images)
        filepath = doc.get('filepath', '')
        if filepath and filepath.startswith('http'):
            import urllib.request as _req
            import io
            from flask import send_file
            try:
                rq = _req.Request(filepath, headers={'User-Agent': 'Mozilla/5.0'})
                with _req.urlopen(rq, timeout=30) as resp:
                    content_type = resp.headers.get('Content-Type', 'application/octet-stream')
                    file_data = resp.read()
                return send_file(
                    io.BytesIO(file_data),
                    as_attachment=True,
                    download_name=doc['filename'],
                    mimetype=content_type,
                )
            except Exception as proxy_exc:
                logger.error("[DOWNLOAD] Proxy failed: %s", proxy_exc)
                # Last resort: redirect to URL directly
                return redirect(filepath)

        flash('File is no longer available. Please ask the admin to re-upload it.', 'warning')
        return redirect(url_for('doc.dashboard'))
    except Exception as exc:
        logger.error("[DOWNLOAD] Error: %s", exc)
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
        # Delete from Cloudinary if it's a Cloudinary URL
        filepath = doc.get('filepath', '')
        if filepath and filepath.startswith('http') and 'cloudinary.com' in filepath:
            try:
                # Extract public_id from URL for Cloudinary deletion
                parts    = filepath.rsplit('/', 1)
                pub_id   = parts[-1].rsplit('.', 1)[0] if parts else None
                if pub_id:
                    cloudinary.uploader.destroy(pub_id, resource_type='auto')
                    logger.info("[HARD-DELETE] Cloudinary asset deleted: %s", pub_id)
            except Exception as cld_exc:
                logger.warning("[HARD-DELETE] Cloudinary delete failed: %s", cld_exc)

        # Wipe from PostgreSQL
        delete_document(doc_id, soft=False)
        flash('Document permanently deleted.', 'success')
    except Exception as e:
        logger.error("[HARD-DELETE] Error: %s", e)
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
    cur  = conn.cursor()
    cur.execute('''
        SELECT d.id, d.filename, d.description, d.tags, u.name AS user_name
        FROM documents d
        JOIN users u ON d.uploaded_by = u.id
        WHERE d.family_id=%s AND d.is_deleted=0
          AND (LOWER(d.filename) LIKE %s OR LOWER(d.description) LIKE %s OR LOWER(d.tags) LIKE %s)
        ORDER BY d.upload_date DESC LIMIT 10
    ''', (family_id, f'%{q}%', f'%{q}%', f'%{q}%'))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    results = []
    for r in rows:
        if role == 'admin' or can_user_view(r['id'], user_id, role):
            results.append({
                'id':          r['id'],
                'filename':    r['filename'],
                'description': r['description'],
                'user_name':   r['user_name'],
                'tags':        r['tags'],
            })
    return jsonify(results)


# ── API: Analytics ────────────────────────────────────────────────────────────

@doc_bp.route('/api/analytics')
@admin_required
def api_analytics():
    return jsonify(get_analytics(session['family_id']))