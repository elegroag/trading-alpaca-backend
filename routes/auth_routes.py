from typing import Any

from flask import Flask, jsonify, request

from utils.auth_utils import require_auth  # noqa: F401 (puede usarse en el futuro)
from config import config
from models.user import (
    User,
    create_user,
    get_user_by_email,
    update_user_last_login,
)
from utils.security import hash_password, verify_password, generate_jwt, encrypt_text


def register_auth_routes(app: Flask) -> None:
    @app.route('/api/auth/register', methods=['POST'])
    def register():
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''

        if not email or '@' not in email:
            return jsonify({'success': False, 'error': 'Email inválido'}), 400

        if len(password) < 8:
            return jsonify({'success': False, 'error': 'Password demasiado corta'}), 400

        if get_user_by_email(email) is not None:
            return jsonify({'success': False, 'error': 'El email ya está registrado'}), 400

        password_hash = hash_password(password)
        nombre = data.get('nombre')
        apellido = data.get('apellido')
        alpaca_api_key = (data.get('alpaca_api_key') or '').strip()
        alpaca_secret_key = (data.get('alpaca_secret_key') or '').strip()
        alpaca_base_url = data.get('alpaca_base_url') or config.ALPACA_BASE_URL

        if not alpaca_api_key or not alpaca_secret_key:
            return jsonify({
                'success': False,
                'error': 'alpaca_api_key y alpaca_secret_key son requeridas',
            }), 400

        alpaca_api_key_enc = encrypt_text(alpaca_api_key)
        alpaca_secret_key_enc = encrypt_text(alpaca_secret_key)

        user = User(
            id=None,
            email=email,
            password_hash=password_hash,
            nombre=nombre,
            apellido=apellido,
            alpaca_api_key_enc=alpaca_api_key_enc,
            alpaca_secret_key_enc=alpaca_secret_key_enc,
            alpaca_base_url=alpaca_base_url,
            paper_trading=True,
        )

        user = create_user(user)

        return jsonify({
            'success': True,
            'data': user.to_dict(),
        }), 201

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''

        if not email or not password:
            return jsonify({'success': False, 'error': 'Email y password son requeridos'}), 400

        user = get_user_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401

        token = generate_jwt(user.id, user.email, user.rol)
        update_user_last_login(user.id)

        return jsonify({
            'success': True,
            'data': {
                'token': token,
                'user': user.to_dict(),
            },
        })
