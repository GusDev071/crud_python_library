from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import JWTExtendedException
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta, timezone

from app import db
from app.models import Book, User
from app.utils.uploads import save_image_from_data_uri

api_bp = Blueprint('api', __name__, url_prefix='/api')


def _book_to_dict(book: Book) -> dict:
    return {
        'id': book.id,
        'title': book.title,
        'author': book.author,
        'stock': book.stock,
        'price': book.price,
        'description': book.description,
        'category': book.category,
        'status': book.status,
        'image_url': book.image_url,
    }


def _parse_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', '1', 'yes', 'si'}:
            return True
        if normalized in {'false', '0', 'no'}:
            return False
    return bool(value)


def _to_utc_iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _public_image_url(filename: str) -> str:
    return f"{request.host_url.rstrip('/')}/public/storage/{filename}"


@api_bp.errorhandler(HTTPException)
def handle_http_exception(error: HTTPException):
    return jsonify({'error': error.description}), error.code


@api_bp.errorhandler(JWTExtendedException)
def handle_jwt_exception(error: JWTExtendedException):
    return jsonify({'error': str(error)}), 401


@api_bp.route('/health', methods=['GET'])
def health():
    return jsonify({'message': 'API funcionando'}), 200


@api_bp.route('/auth/register', methods=['POST'])
def register_user():
    if not request.is_json:
        return jsonify({'error': 'El body debe ser JSON'}), 400

    payload = request.get_json(silent=True) or {}
    username = payload.get('username', '').strip()
    password = payload.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'username y password son requeridos'}), 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'error': 'El usuario ya existe'}), 409

    new_user = User(username=username, password=generate_password_hash(password))
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'Usuario creado', 'user': {'id': new_user.id, 'username': new_user.username}}), 201


@api_bp.route('/auth/login', methods=['POST'])
def login_user():
    if not request.is_json:
        return jsonify({'error': 'El body debe ser JSON'}), 400

    payload = request.get_json(silent=True) or {}
    username = payload.get('username', '').strip()
    password = payload.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'username y password son requeridos'}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'error': 'Credenciales inválidas'}), 401

    session_started_at = datetime.now(timezone.utc)
    session_expires_at = session_started_at + timedelta(hours=1)

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={'username': user.username},
        expires_delta=timedelta(hours=1)
    )
    return jsonify({
        'message': 'Login correcto',
        'access_token': access_token,
        'token_type': 'Bearer',
        'sessionStartedAt': _to_utc_iso(session_started_at),
        'sessionExpiresAt': _to_utc_iso(session_expires_at),
        'user': {'id': user.id, 'username': user.username},
    }), 200


@api_bp.route('/auth/me', methods=['GET'])
@jwt_required()
def me():
    current_user_id = get_jwt_identity()
    try:
        user_id = int(current_user_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'Token inválido'}), 401

    user = User.query.get_or_404(user_id)
    return jsonify({'data': {'id': user.id, 'username': user.username}}), 200


@api_bp.route('/uploads/image', methods=['POST'])
@jwt_required()
def upload_image():
    if not request.is_json:
        return jsonify({'error': 'El body debe ser JSON'}), 400

    payload = request.get_json(silent=True) or {}
    image_data_uri = payload.get('imageDataUri') or payload.get('logoDataUri')
    if not image_data_uri:
        return jsonify({'error': 'imageDataUri es requerido'}), 400

    try:
        filename = save_image_from_data_uri(
            data_uri=image_data_uri,
            storage_dir=current_app.config['STORAGE_DIR'],
        )
    except ValueError as error:
        return jsonify({'error': str(error)}), 400

    public_url = _public_image_url(filename)
    return jsonify({'message': 'Imagen subida', 'data': {'filename': filename, 'public_url': public_url}}), 201


@api_bp.route('/books', methods=['GET'])
@jwt_required()
def list_books():
    books = Book.query.all()
    return jsonify({'data': [_book_to_dict(book) for book in books]}), 200


@api_bp.route('/books/<int:book_id>', methods=['GET'])
@jwt_required()
def get_book(book_id: int):
    book = Book.query.get_or_404(book_id)
    return jsonify({'data': _book_to_dict(book)}), 200


@api_bp.route('/books', methods=['POST'])
@jwt_required()
def create_book():
    if not request.is_json:
        return jsonify({'error': 'El body debe ser JSON'}), 400

    payload = request.get_json(silent=True) or {}

    title = str(payload.get('title', '')).strip()
    author = str(payload.get('author', '')).strip()

    if not title or not author:
        return jsonify({'error': 'title y author son requeridos'}), 400

    try:
        stock = int(payload.get('stock', 0))
        price = float(payload.get('price', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'stock debe ser entero y price numérico'}), 400

    status = _parse_bool(payload.get('status'), default=True)
    description = payload.get('description')
    category = payload.get('category')

    if description is not None:
        description = str(description).strip()
    if category is not None:
        category = str(category).strip()

    image_url = None
    image_data_uri = payload.get('imageDataUri') or payload.get('logoDataUri')
    if image_data_uri:
        try:
            filename = save_image_from_data_uri(
                data_uri=image_data_uri,
                storage_dir=current_app.config['STORAGE_DIR'],
            )
        except ValueError as error:
            return jsonify({'error': str(error)}), 400
        image_url = _public_image_url(filename)

    new_book = Book(
        title=title,
        author=author,
        stock=stock,
        price=price,
        description=description,
        category=category,
        status=status,
        image_url=image_url,
    )
    db.session.add(new_book)
    db.session.commit()

    return jsonify({'message': 'Libro creado', 'data': _book_to_dict(new_book)}), 201


@api_bp.route('/books/<int:book_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_book(book_id: int):
    if not request.is_json:
        return jsonify({'error': 'El body debe ser JSON'}), 400

    book = Book.query.get_or_404(book_id)
    payload = request.get_json(silent=True) or {}

    if not payload:
        return jsonify({'error': 'Debes enviar al menos un campo para actualizar'}), 400

    if 'title' in payload:
        book.title = str(payload.get('title', '')).strip()
    if 'author' in payload:
        book.author = str(payload.get('author', '')).strip()
    if 'stock' in payload:
        try:
            book.stock = int(payload.get('stock'))
        except (TypeError, ValueError):
            return jsonify({'error': 'stock debe ser entero'}), 400
    if 'price' in payload:
        try:
            book.price = float(payload.get('price'))
        except (TypeError, ValueError):
            return jsonify({'error': 'price debe ser numérico'}), 400
    if 'status' in payload:
        book.status = _parse_bool(payload.get('status'), default=book.status)
    if 'description' in payload:
        description = payload.get('description')
        book.description = str(description).strip() if description is not None else None
    if 'category' in payload:
        category = payload.get('category')
        book.category = str(category).strip() if category is not None else None

    if 'imageDataUri' in payload or 'logoDataUri' in payload:
        image_data_uri = payload.get('imageDataUri') or payload.get('logoDataUri')
        if image_data_uri:
            try:
                filename = save_image_from_data_uri(
                    data_uri=image_data_uri,
                    storage_dir=current_app.config['STORAGE_DIR'],
                )
            except ValueError as error:
                return jsonify({'error': str(error)}), 400
            book.image_url = _public_image_url(filename)
        else:
            book.image_url = None

    if not book.title or not book.author:
        return jsonify({'error': 'title y author no pueden quedar vacíos'}), 400

    db.session.commit()
    return jsonify({'message': 'Libro actualizado', 'data': _book_to_dict(book)}), 200


@api_bp.route('/books/<int:book_id>', methods=['DELETE'])
@jwt_required()
def delete_book(book_id: int):
    book = Book.query.get_or_404(book_id)
    db.session.delete(book)
    db.session.commit()
    return jsonify({'message': 'Libro eliminado'}), 200
