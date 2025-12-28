from flask import Flask, jsonify, request, g

from utils.auth_utils import require_auth

from services.trend_preferences_service import (
    trend_preferences_service,
    TrendPreferencesServiceException,
)
from models.user import update_user_keys
from utils.security import encrypt_text


def register_user_routes(app: Flask) -> None:
    @app.route('/api/user/me', methods=['GET'])
    @require_auth
    def get_me():
        user = g.current_user
        return jsonify({
            'success': True,
            'data': user.to_dict(),
        })

    @app.route('/api/user/trend-preferences', methods=['GET'])
    @require_auth
    def get_trend_preferences():
        try:
            prefs = trend_preferences_service.get_preferences(g.current_user.id)
            return jsonify({'success': True, 'data': prefs})
        except TrendPreferencesServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/api/user/keys', methods=['PUT'])
    @require_auth
    def update_keys():
        data = request.get_json() or {}

        alpaca_api_key = data.get('alpaca_api_key')
        alpaca_secret_key = data.get('alpaca_secret_key')
        alpaca_base_url = data.get('alpaca_base_url')
        paper_trading = data.get('paper_trading')

        alpaca_api_key_enc = None
        alpaca_secret_key_enc = None

        if alpaca_api_key is not None:
            alpaca_api_key_enc = encrypt_text(alpaca_api_key) if alpaca_api_key else ''

        if alpaca_secret_key is not None:
            alpaca_secret_key_enc = encrypt_text(alpaca_secret_key) if alpaca_secret_key else ''

        paper_trading_value = None
        if paper_trading is not None:
            if isinstance(paper_trading, bool):
                paper_trading_value = paper_trading
            else:
                paper_trading_value = str(paper_trading).lower() == 'true'

        user = update_user_keys(
            g.current_user.id,
            alpaca_api_key_enc=alpaca_api_key_enc,
            alpaca_secret_key_enc=alpaca_secret_key_enc,
            alpaca_base_url=alpaca_base_url,
            paper_trading=paper_trading_value,
        )

        if user is None:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404

        return jsonify({
            'success': True,
            'data': user.to_dict(),
        })
