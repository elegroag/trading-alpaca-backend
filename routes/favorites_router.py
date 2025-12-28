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


def register_favorites_routes(app: Flask) -> None:

    @app.route('/api/favorites/test', methods=['GET'])
    @require_auth
    def test_favorites():
        return jsonify({
            'success': True,
            'message': 'Favorites router working',
            'timestamp': str(datetime.now())
        })

    @app.route('/api/favorites/details', methods=['GET'])
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


    @app.route('/api/favorites/refresh', methods=['POST'])
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


    @app.route('/api/favorites/trend', methods=['POST'])
    @require_auth
    def get_favorite_trend():
        print(f"[FAVORITES] Trend endpoint called at {datetime.now()}")
        data = request.get_json() or {}
        print(f"[FAVORITES] Request data: {data}")
        
        symbol = data.get('symbol')
        profile = data.get('profile')
        model_type = data.get('model_type')
        
        print(f"[FAVORITES] Parsed - symbol: {symbol}, profile: {profile}, model_type: {model_type}")

        if not symbol or not isinstance(symbol, str):
            print(f"[FAVORITES] Invalid symbol: {symbol}")
            return jsonify({
                'success': False,
                'error': 'Debe enviar un símbolo válido en el campo "symbol"',
            }), 400

        sym = str(symbol).strip().upper()
        if not sym:
            print(f"[FAVORITES] Empty symbol after processing")
            return jsonify({
                'success': False,
                'error': 'Símbolo vacío',
            }), 400

        print(f"[FAVORITES] Processing symbol: {sym}")
        
        try:
            print(f"[FAVORITES] About to call trend_detection_service.analyze_symbol")
            result = trend_detection_service.analyze_symbol(
                sym,
                user=g.current_user,
                profile=profile,
                model_type=model_type,
            )
            print(f"[FAVORITES] Analysis completed successfully")
            
            try:
                print(f"[FAVORITES] Saving preferences")
                saved = trend_preferences_service.set_preferences(
                    g.current_user.id,
                    profile=result.get('profile'),
                    model_type=result.get('model_type'),
                )
                result['profile'] = saved.get('profile', result.get('profile'))
                result['model_type'] = saved.get('model_type', result.get('model_type'))
                print(f"[FAVORITES] Preferences saved successfully")
            except TrendPreferencesServiceException as pref_e:
                print(f"[FAVORITES] Warning saving preferences: {pref_e}")
                # Si falla el guardado de preferencias, no rompemos el flujo principal
                pass
                
            print(f"[FAVORITES] Returning successful response")
            return jsonify({
                'success': True,
                'data': result,
            })
        except TrendDetectionServiceException as e:
            print(f"[FAVORITES] TrendDetectionServiceException: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
            }), 400
        except Exception as e:
            print(f"[FAVORITES] General Exception: {e}")
            import traceback
            print(f"[FAVORITES] Traceback: {traceback.format_exc()}")
            return jsonify({
                'success': False,
                'error': f'Error interno del servidor: {str(e)}',
            }), 500

