from flask import Flask, jsonify, request, g

from utils.auth_utils import require_auth
from services.market_screener_service import (
    market_screener_service,
    MarketScreenerServiceException,
)
from services.market_symbol_service import (
    market_symbol_service,
    MarketSymbolServiceException,
)
from models.market_symbol import list_symbols as list_market_symbols


def register_screener_routes(app: Flask) -> None:
    @app.route('/api/screener/most-actives', methods=['GET'])
    @require_auth
    def screener_most_actives():
        """Obtiene las acciones más activas usando Alpaca Screener API."""
        try:
            by = request.args.get('by', 'volume').lower()
            top_param = request.args.get('limit', request.args.get('top', '10'))
            market = request.args.get('market', 'stocks').lower()
            min_price_raw = request.args.get('min_price')
            max_price_raw = request.args.get('max_price')

            try:
                top = int(top_param)
            except (TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'error': 'Parámetro limit/top debe ser un número entero',
                }), 400

            min_price = None
            max_price = None
            try:
                if min_price_raw is not None and min_price_raw != '':
                    min_price = float(min_price_raw)
                if max_price_raw is not None and max_price_raw != '':
                    max_price = float(max_price_raw)
            except (TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'error': 'Parámetros min_price/max_price deben ser numéricos',
                }), 400

            items = market_screener_service.get_most_actives(
                user=g.current_user,
                by=by,
                top=top,
                market=market,
                min_price=min_price,
                max_price=max_price,
            )

            # Alimentar colección de símbolos de mercado en segundo plano
            try:
                market_symbol_service.upsert_from_most_actives(items)
            except MarketSymbolServiceException:
                # No interrumpir la respuesta principal del screener si falla Mongo
                pass

            return jsonify({'success': True, 'data': items})
        except MarketScreenerServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Error interno del servidor',
            }), 500

    @app.route('/api/screener/market-movers', methods=['GET'])
    @require_auth
    def screener_market_movers():
        """Obtiene los top market movers (ganadores y perdedores)."""
        try:
            top_param = request.args.get('limit', request.args.get('top', '10'))
            market = request.args.get('market', 'stocks').lower()
            min_price_raw = request.args.get('min_price')
            max_price_raw = request.args.get('max_price')

            try:
                top = int(top_param)
            except (TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'error': 'Parámetro limit/top debe ser un número entero',
                }), 400

            min_price = None
            max_price = None
            try:
                if min_price_raw is not None and min_price_raw != '':
                    min_price = float(min_price_raw)
                if max_price_raw is not None and max_price_raw != '':
                    max_price = float(max_price_raw)
            except (TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'error': 'Parámetros min_price/max_price deben ser numéricos',
                }), 400

            data = market_screener_service.get_market_movers(
                user=g.current_user,
                top=top,
                market=market,
                min_price=min_price,
                max_price=max_price,
            )

            return jsonify({'success': True, 'data': data})
        except MarketScreenerServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Error interno del servidor',
            }), 500

    @app.route('/api/screener/sync-symbols', methods=['POST'])
    @require_auth
    def screener_sync_symbols():
        try:
            payload = request.get_json(silent=True) or {}

            top_most_actives_raw = (
                payload.get('top_most_actives')
                or request.args.get('top_most_actives')
                or request.args.get('limit')
                or '50'
            )
            top_movers_raw = (
                payload.get('top_movers')
                or request.args.get('top_movers')
                or '50'
            )
            market = (payload.get('market') or request.args.get('market') or 'stocks').lower()

            try:
                top_most_actives = int(top_most_actives_raw)
                top_movers = int(top_movers_raw)
            except (TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'error': 'Parámetros top_most_actives/top_movers deben ser enteros',
                }), 400

            processed = market_symbol_service.sync_from_screener(
                user=g.current_user,
                top_most_actives=top_most_actives,
                top_movers=top_movers,
                market=market,
            )

            return jsonify({'success': True, 'data': {'processed': processed}})
        except MarketSymbolServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Error interno del servidor',
            }), 500

    @app.route('/api/market-symbols', methods=['GET'])
    @require_auth
    def list_market_symbols_api():
        try:
            limit_param = request.args.get('limit', '1000')
            try:
                limit = int(limit_param)
            except (TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'error': 'Parámetro limit debe ser un número entero',
                }), 400

            symbols = list_market_symbols(limit=limit)
            data = [s.to_dict() for s in symbols]
            return jsonify({'success': True, 'data': data})
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Error interno del servidor',
            }), 500
