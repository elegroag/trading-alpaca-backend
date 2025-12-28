from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import bcrypt
import jwt
from cryptography.fernet import Fernet

from config import config


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def _get_fernet() -> Fernet:
    key = config.FERNET_KEY
    return Fernet(key.encode("utf-8"))


def encrypt_text(plaintext: str) -> str:
    if plaintext is None:
        return ""
    fernet = _get_fernet()
    token = fernet.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(token: str) -> str:
    if not token:
        return ""
    fernet = _get_fernet()
    value = fernet.decrypt(token.encode("utf-8"))
    return value.decode("utf-8")


def generate_jwt(user_id: str, email: str, role: str) -> str:
    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRES_MIN),
    }
    token = jwt.encode(payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    if isinstance(token, bytes):
        return token.decode("utf-8")
    return token


def decode_jwt(token: str) -> Dict[str, Any]:
    payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    return payload
