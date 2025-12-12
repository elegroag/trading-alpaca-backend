from functools import wraps
from typing import Callable, TypeVar, Any

from flask import request, jsonify, g

from models.user import get_user_by_id
from utils.security import decode_jwt

F = TypeVar("F", bound=Callable[..., Any])


def require_auth(f: F) -> F:
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return (
                jsonify({"success": False, "error": "Autenticación requerida"}),
                401,
            )

        token = auth_header.split(" ", 1)[1].strip()

        try:
            payload = decode_jwt(token)
        except Exception:
            return (
                jsonify({"success": False, "error": "Token inválido o expirado"}),
                401,
            )

        user_id = payload.get("sub")
        if not user_id:
            return jsonify({"success": False, "error": "Token inválido"}), 401

        user = get_user_by_id(user_id)
        if not user:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
