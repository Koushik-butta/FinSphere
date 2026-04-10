import os
from flask import Flask
from config import SECRET_KEY, UPLOAD_FOLDER
from database import init_db
from routes.auth_routes import auth_bp
from routes.document_routes import doc_bp
from routes.category_routes import cat_bp

app = Flask(__name__, static_folder='static')
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

init_db()

app.register_blueprint(auth_bp)
app.register_blueprint(doc_bp)
app.register_blueprint(cat_bp)

if __name__ == '__main__':
    app.run(debug=True)
