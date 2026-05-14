import base64
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

DATA_URI_PATTERN = re.compile(r'^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$', re.DOTALL)

ALLOWED_MIME_TO_EXT = {
    'image/png': 'png',
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/webp': 'webp',
    'image/gif': 'gif',
}


def save_image_from_data_uri(data_uri: str, storage_dir: str) -> str:
    if not isinstance(data_uri, str) or not data_uri.strip():
        raise ValueError('imageDataUri es requerido')

    match = DATA_URI_PATTERN.match(data_uri.strip())
    if not match:
        raise ValueError('Formato inválido. Debe ser Data URI base64 de imagen')

    mime_type = match.group(1).lower()
    base64_data = match.group(2).strip()

    extension = ALLOWED_MIME_TO_EXT.get(mime_type)
    if not extension:
        raise ValueError('Tipo de imagen no permitido. Usa png, jpg, jpeg, webp o gif')

    try:
        binary_data = base64.b64decode(base64_data, validate=True)
    except (ValueError, base64.binascii.Error):
        raise ValueError('El contenido base64 de la imagen es inválido')

    if not binary_data:
        raise ValueError('La imagen está vacía')

    os.makedirs(storage_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    filename = f"img_{timestamp}_{uuid4().hex[:10]}.{extension}"
    full_path = os.path.join(storage_dir, filename)

    with open(full_path, 'wb') as image_file:
        image_file.write(binary_data)

    return filename
