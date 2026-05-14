import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import timedelta

db = SQLAlchemy()
jwt = JWTManager()


def _apply_sqlite_migrations() -> None:
    # Migra esquema existente sin borrar datos cuando faltan columnas nuevas.
    table_exists = db.session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='book'")
    ).fetchone()
    if not table_exists:
        return

    columns_info = db.session.execute(text("PRAGMA table_info(book)")).fetchall()
    existing_columns = {column[1] for column in columns_info}

    if 'price' not in existing_columns:
        db.session.execute(text("ALTER TABLE book ADD COLUMN price FLOAT NOT NULL DEFAULT 0"))
    
    if 'description' not in existing_columns:
        db.session.execute(text("ALTER TABLE book ADD COLUMN description TEXT"))
    
    if 'category' not in existing_columns:
        db.session.execute(text("ALTER TABLE book ADD COLUMN category VARCHAR(100)"))

    if 'status' not in existing_columns:
        db.session.execute(text("ALTER TABLE book ADD COLUMN status BOOLEAN NOT NULL DEFAULT 1"))

    if 'image_url' not in existing_columns:
        db.session.execute(text("ALTER TABLE book ADD COLUMN image_url VARCHAR(255)"))

    db.session.commit()

def create_app():
    app = Flask(__name__, template_folder='../templates')

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    storage_dir = os.path.join(base_dir, 'storage')
    os.makedirs(storage_dir, exist_ok=True)

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
    app.config['SECRET_KEY'] = '677bb700d30be377c35cb7aedaa170b82890d722a00f60a0073cbac21bb5cf9c'
    app.config['JWT_SECRET_KEY'] = app.config['SECRET_KEY']
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['STORAGE_DIR'] = storage_dir

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    "http://localhost:4200",
                    "http://127.0.0.1:4200",
                ]
            }
        },
        supports_credentials=True,
        allow_headers=["Authorization", "Content-Type"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    db.init_app(app)
    jwt.init_app(app)

    @jwt.unauthorized_loader
    def unauthorized_callback(_message):
        return jsonify({'error': 'Token requerido'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(_message):
        return jsonify({'error': 'Token inválido'}), 401

    @jwt.expired_token_loader
    def expired_token_callback(_jwt_header, _jwt_payload):
        return jsonify({'error': 'Token expirado'}), 401

    @app.route('/public/storage/<path:filename>', methods=['GET'])
    def public_storage(filename):
        return send_from_directory(app.config['STORAGE_DIR'], filename)

    from app.routes.auth import auth_bp
    from app.routes.books import books_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()
        _apply_sqlite_migrations()

    return app
