import os

SECRET_KEY    = os.environ.get('SECRET_KEY', 'smart_family_finance_secret_key_2024')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
DB_FILE       = os.environ.get('DB_FILE', 'database.db')

# Email is now handled via Brevo HTTP API.
# Set BREVO_API_KEY and SENDER_EMAIL as environment variables in Render dashboard.
# No SMTP settings needed.