"""
app.py — FinSphere Flask application entry point.

Production-hardened for Render:
  - Structured logging
  - Startup env-var validation
  - /health endpoint (used by Render's health checks AND keep-alive pinger)
  - Global error handlers (404, 500, DB errors, Cloudinary errors)
  - Keep-alive background thread (prevents Render sleep)
"""

import os
import sys
import logging
from flask import Flask, jsonify, request

# ── Logging setup (must be first so other modules inherit the config) ─────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── Startup: validate required environment variables ─────────────────────────
_REQUIRED_ENV = [
    "DATABASE_URL",
    "SECRET_KEY",
    "CLOUDINARY_CLOUD_NAME",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_API_SECRET",
]

_missing = [v for v in _REQUIRED_ENV if not os.environ.get(v)]
if _missing:
    logger.error(
        "FATAL — missing required environment variables: %s\n"
        "Set them in the Render dashboard under Environment → Environment Variables.",
        ", ".join(_missing)
    )
    # Don't crash entirely — allow the app to start so /health still responds
    # and you can see the error in Render logs rather than a pure silent crash.

# ── Config & Cloudinary ───────────────────────────────────────────────────────
from config import (
    SECRET_KEY, DATABASE_URL,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET,
)

import cloudinary
if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
    )
    logger.info("Cloudinary configured — cloud: %s", CLOUDINARY_CLOUD_NAME)
else:
    logger.warning("Cloudinary NOT configured — uploads will fail!")

# ── Database init ─────────────────────────────────────────────────────────────
from database import init_db

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='static')
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024   # 16 MB max upload

# ── Session security ──────────────────────────────────────────────────────────
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE']   = os.environ.get('FLASK_ENV') == 'production'

# ── Init database ─────────────────────────────────────────────────────────────
try:
    with app.app_context():
        init_db()
    logger.info("Database initialised successfully.")
except Exception as exc:
    logger.error("Database init failed: %s", exc)

# ── Register blueprints ───────────────────────────────────────────────────────
from routes.auth_routes     import auth_bp
from routes.document_routes import doc_bp
from routes.category_routes import cat_bp

app.register_blueprint(auth_bp)
app.register_blueprint(doc_bp)
app.register_blueprint(cat_bp)

# ── Health check endpoint ─────────────────────────────────────────────────────
@app.route('/health')
def health():
    """
    Keep-alive + Render health-check endpoint.
    Returns 200 immediately — no DB call so it never hangs.
    """
    return jsonify({"status": "ok", "service": "FinSphere"}), 200

# ── Security headers ──────────────────────────────────────────────────────────
@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options']        = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy']        = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy']     = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src  'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src   'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "img-src    'self' data: https://res.cloudinary.com; "
        "frame-src  'self' https://res.cloudinary.com;"
    )
    return response

# ── Global error handlers ─────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    logger.warning("404 Not Found: %s %s", request.method, request.path)
    if request.path.startswith('/api/'):
        return jsonify({"error": "Not found", "status": 404}), 404
    from flask import render_template
    try:
        return render_template('errors/404.html'), 404
    except Exception:
        return "<h2>404 — Page not found</h2><a href='/'>Home</a>", 404

@app.errorhandler(500)
def internal_error(e):
    logger.error("500 Internal Server Error: %s", e)
    if request.path.startswith('/api/'):
        return jsonify({"error": "Internal server error", "status": 500}), 500
    from flask import render_template
    try:
        return render_template('errors/500.html'), 500
    except Exception:
        return "<h2>500 — Something went wrong</h2><a href='/'>Home</a>", 500

@app.errorhandler(413)
def file_too_large(e):
    from flask import flash, redirect, url_for
    flash("File too large. Maximum upload size is 16 MB.", "danger")
    return redirect(url_for('doc.upload'))

try:
    import psycopg2
    @app.errorhandler(psycopg2.Error)
    def database_error(e):
        logger.error("Database error: %s", e)
        if request.path.startswith('/api/'):
            return jsonify({"error": "Database unavailable", "status": 503}), 503
        from flask import flash, redirect, url_for
        flash("A database error occurred. Please try again in a moment.", "danger")
        return redirect(url_for('auth.index'))
except Exception:
    pass

# ── Start keep-alive pinger (prevents Render sleep) ───────────────────────────
from keepalive import start_keepalive
start_keepalive()

# ── Dev server ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
