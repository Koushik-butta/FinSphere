import os

# ── Secret Key ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'smart_family_finance_secret_key')

# ── File Upload ───────────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')

# ── PostgreSQL Database (Neon / any PostgreSQL) ───────────────────────────────
# Replace the fallback string below with your Neon connection string,
# or set the DATABASE_URL environment variable in production.
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://neondb_owner:npg_t1TYHapPze3m@ep-billowing-morning-anoyvtoh.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require'
)

# ── Email settings (Brevo API) ────────────────────────────────────────────────
# Using Brevo to allow sending to any user without a custom domain.
SENDER_EMAIL  = os.environ.get('SENDER_EMAIL', 'b.kowshik2007@gmail.com')
SENDER_NAME   = "Family Finance"
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')

# ── Session Security ──────────────────────────────────────────────────────────
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
# Set to True in production (HTTPS only):
SESSION_COOKIE_SECURE   = os.environ.get('FLASK_ENV') == 'production'

# ── Cloudinary Storage ────────────────────────────────────────────────────────
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY    = os.environ.get('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')