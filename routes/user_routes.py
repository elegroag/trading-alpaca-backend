from typing import Any
from datetime import datetime

from flask import Flask, jsonify, request, g

from utils.auth_utils import require_auth
from services.symbol_preferences_service import (
    symbol_preferences_service,
    SymbolPreferencesServiceException,
)
from services.market_symbol_service import (
    market_symbol_service,
    MarketSymbolServiceException,
)
from services.trend_detection_service import (
    trend_detection_service,
    TrendDetectionServiceException,
)
from services.trend_preferences_service import (
    trend_preferences_service,
    TrendPreferencesServiceException,
)
from models.market_symbol import get_symbol_by_symbol
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

    @app.route('/api/user/preferences/symbols', methods=['GET'])
    @require_auth
    def get_symbol_preferences():
        try:
            symbols = symbol_preferences_service.get_symbols(g.current_user.id)
            return jsonify({
                'success': True,
                'data': symbols,
            })
        except SymbolPreferencesServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/api/user/favorites/details', methods=['GET'])
    @require_auth
    def get_favorite_details():
        """Devuelve detalles de mercado de los símbolos favoritos usando market_symbols.

        Usa la colección de Mongo como caché y solo actualiza desde Alpaca cuando el
        símbolo no existe o no se ha actualizado en la fecha actual.
        """
        try:
            symbols = symbol_preferences_service.get_symbols(g.current_user.id)

            normalized: list[str] = []
            for s in symbols:
                if s is None:
                    continue
                sym = str(s).strip().upper()
                if not sym:
                    continue
                if sym not in normalized:
                    normalized.append(sym)

            result: list[dict[str, Any]] = []

            for sym in normalized:
                doc = get_symbol_by_symbol(sym)
                needs_refresh = True

                if doc is not None and isinstance(getattr(doc, 'updated_at', None), datetime):
                    try:
                        if doc.updated_at.date() == datetime.utcnow().date():
                            needs_refresh = False
                    except Exception:
                        needs_refresh = True

                if needs_refresh:
                    try:
                        market_symbol_service.sync_single_symbol_from_quote(sym, user=g.current_user)
                        refreshed = get_symbol_by_symbol(sym)
                        if refreshed is not None:
                            doc = refreshed
                    except MarketSymbolServiceException:
                        # Si falla Alpaca/Mongo, seguimos con el doc previo si existía
                        pass

                if doc is not None:
                    result.append(doc.to_dict())

            return jsonify({'success': True, 'data': result})
        except SymbolPreferencesServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

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

    @app.route('/api/user/favorites/refresh', methods=['POST'])
    @require_auth
    def refresh_favorites():
        """Fuerza la actualización de todos los símbolos favoritos desde Alpaca."""
        try:
            symbols = symbol_preferences_service.get_symbols(g.current_user.id)

            normalized: list[str] = []
            for s in symbols:
                if s is None:
                    continue
                sym = str(s).strip().upper()
                if not sym:
                    continue
                if sym not in normalized:
                    normalized.append(sym)

            result: list[dict[str, Any]] = []
            errors: list[str] = []

            for sym in normalized:
                try:
                    market_symbol_service.sync_single_symbol_from_quote(sym, user=g.current_user)
                    refreshed = get_symbol_by_symbol(sym)
                    if refreshed is not None:
                        result.append(refreshed.to_dict())
                except MarketSymbolServiceException as e:
                    errors.append(f"{sym}: {str(e)}")

            return jsonify({
                'success': True,
                'data': result,
                'errors': errors if errors else None,
            })
        except SymbolPreferencesServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/api/user/preferences/symbols', methods=['PUT'])
    @require_auth
    def set_symbol_preferences():
        data = request.get_json() or {}
        symbols = data.get('symbols')

        if symbols is None or not isinstance(symbols, list):
            return jsonify({
                'success': False,
                'error': 'El campo symbols debe ser una lista',
            }), 400

        try:
            updated = symbol_preferences_service.set_symbols(g.current_user.id, symbols)
            return jsonify({
                'success': True,
                'data': updated,
            })
        except SymbolPreferencesServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/api/user/favorites/trend', methods=['POST'])
    @require_auth
    def get_favorite_trend():
        data = request.get_json() or {}
        symbol = data.get('symbol')
        profile = data.get('profile')
        model_type = data.get('model_type')

        if not symbol or not isinstance(symbol, str):
            return jsonify({
                'success': False,
                'error': 'Debe enviar un símbolo válido en el campo "symbol"',
            }), 400

        sym = str(symbol).strip().upper()
        if not sym:
            return jsonify({
                'success': False,
                'error': 'Símbolo vacío',
            }), 400

        try:
            result = trend_detection_service.analyze_symbol(
                sym,
                user=g.current_user,
                profile=profile,
                model_type=model_type,
            )
            try:
                saved = trend_preferences_service.set_preferences(
                    g.current_user.id,
                    profile=result.get('profile'),
                    model_type=result.get('model_type'),
                )
                result['profile'] = saved.get('profile', result.get('profile'))
                result['model_type'] = saved.get('model_type', result.get('model_type'))
            except TrendPreferencesServiceException:
                # Si falla el guardado de preferencias, no rompemos el flujo principal
                pass
            return jsonify({
                'success': True,
                'data': result,
            })
        except TrendDetectionServiceException as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 400
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': f'Error interno del servidor: {str(e)}',
            }), 500

    @app.route('/api/user/preferences/symbols', methods=['POST'])
    @require_auth
    def add_symbol_preferences():
        data = request.get_json() or {}

        symbols = data.get('symbols')
        symbol = data.get('symbol')

        if symbols is None and symbol is None:
            return jsonify({
                'success': False,
                'error': 'Debe enviar symbol o symbols',
            }), 400

        if symbols is not None and not isinstance(symbols, list):
            return jsonify({
                'success': False,
                'error': 'El campo symbols debe ser una lista',
            }), 400

        symbols_list = symbols or []
        if symbol is not None:
            symbols_list.append(symbol)

        try:
            updated = symbol_preferences_service.add_symbols(g.current_user.id, symbols_list)

            # Alimentar colección de símbolos de mercado para los símbolos añadidos
            try:
                # Normalizar y evitar duplicados simples a nivel de ruta
                norm_set = set()
                for s in symbols_list:
                    if s is None:
                        continue
                    sym = str(s).strip().upper()
                    if not sym:
                        continue
                    if sym in norm_set:
                        continue
                    norm_set.add(sym)
                    market_symbol_service.sync_single_symbol_from_quote(sym, user=g.current_user)
            except MarketSymbolServiceException:
                # No interrumpir la preferencia de símbolos si falla Mongo/Alpaca
                pass

            return jsonify({
                'success': True,
                'data': updated,
            })
        except SymbolPreferencesServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/api/user/preferences/symbols', methods=['DELETE'])
    @require_auth
    def delete_symbol_preferences():
        data = request.get_json(silent=True) or {}

        symbols = data.get('symbols')
        symbol = data.get('symbol')

        try:
            if symbols is None and symbol is None:
                updated = symbol_preferences_service.clear_symbols(g.current_user.id)
            else:
                if symbols is not None and not isinstance(symbols, list):
                    return jsonify({
                        'success': False,
                        'error': 'El campo symbols debe ser una lista',
                    }), 400

                symbols_list = symbols or []
                if symbol is not None:
                    symbols_list.append(symbol)

                updated = symbol_preferences_service.remove_symbols(g.current_user.id, symbols_list)

            return jsonify({
                'success': True,
                'data': updated,
            })
        except SymbolPreferencesServiceException as e:
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
