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

def register_preferences_routes(app: Flask) -> None:

    @app.route('/api/preferences/symbols', methods=['GET'])
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

    @app.route('/api/preferences/symbols', methods=['PUT'])
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

    @app.route('/api/preferences/symbols', methods=['POST'])
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

    @app.route('/api/preferences/symbols', methods=['DELETE'])
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
