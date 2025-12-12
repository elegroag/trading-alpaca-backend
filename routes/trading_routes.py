from typing import List

from flask import Flask, jsonify, request, g
from flask_socketio import SocketIO

from utils.auth_utils import require_auth
from services.trading_service import trading_service, TradingServiceException
from services.alpaca_service import alpaca_service, AlpacaServiceException
from services.swing_strategy_service import (
    swing_strategy_service,
    SwingStrategyServiceException,
)
from models.order import OrderSide


def register_trading_routes(app: Flask, socketio: SocketIO) -> None:
    @app.route('/api/account', methods=['GET'])
    @require_auth
    def get_account():
        """Obtiene información de la cuenta."""
        try:
            account = trading_service.get_account_info(user=g.current_user)
            return jsonify({'success': True, 'data': account.to_dict()})
        except TradingServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/api/positions', methods=['GET'])
    @require_auth
    def get_positions():
        """Obtiene todas las posiciones abiertas."""
        try:
            positions = trading_service.get_positions(user=g.current_user)
            return jsonify({
                'success': True,
                'data': [pos.to_dict() for pos in positions],
            })
        except TradingServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/api/orders', methods=['GET'])
    @require_auth
    def get_orders():
        """Obtiene órdenes abiertas."""
        try:
            orders = trading_service.get_open_orders(user=g.current_user)
            return jsonify({
                'success': True,
                'data': [order.to_dict() for order in orders],
            })
        except TradingServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/api/orders', methods=['POST'])
    @require_auth
    def create_order():
        """Crea una nueva orden."""
        try:
            data = request.get_json() or {}

            required_fields = ['symbol', 'qty', 'side', 'order_type']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f'Campo requerido faltante: {field}',
                    }), 400

            side = (
                OrderSide.BUY
                if str(data['side']).lower() == 'buy'
                else OrderSide.SELL
            )

            if str(data['order_type']).lower() == 'market':
                order = trading_service.create_market_order(
                    symbol=str(data['symbol']).upper(),
                    qty=float(data['qty']),
                    side=side,
                    user=g.current_user,
                )
            elif str(data['order_type']).lower() == 'limit':
                if 'limit_price' not in data:
                    return jsonify({
                        'success': False,
                        'error': 'limit_price requerido para orden límite',
                    }), 400

                order = trading_service.create_limit_order(
                    symbol=str(data['symbol']).upper(),
                    qty=float(data['qty']),
                    side=side,
                    limit_price=float(data['limit_price']),
                    user=g.current_user,
                )
            else:
                return jsonify({
                    'success': False,
                    'error': f"Tipo de orden no soportado: {data['order_type']}",
                }), 400

            socketio.emit('order_created', order.to_dict())

            return jsonify({'success': True, 'data': order.to_dict()}), 201
        except TradingServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Error interno del servidor',
            }), 500

    @app.route('/api/swing-trade', methods=['POST'])
    @require_auth
    def create_swing_trade():
        """Crea una operación swing trade completa."""
        try:
            data = request.get_json() or {}

            required_fields = [
                'symbol',
                'qty',
                'entry_price',
                'take_profit_price',
                'stop_loss_price',
            ]
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f'Campo requerido faltante: {field}',
                    }), 400

            result = trading_service.create_swing_trade(
                symbol=str(data['symbol']).upper(),
                qty=float(data['qty']),
                entry_price=float(data['entry_price']),
                take_profit_price=float(data['take_profit_price']),
                stop_loss_price=float(data['stop_loss_price']),
                user=g.current_user,
            )

            response_data = {
                'entry_order': result['entry'].to_dict(),
                'take_profit_target': result['take_profit_target'],
                'stop_loss_target': result['stop_loss_target'],
            }

            socketio.emit('swing_trade_created', response_data)

            return jsonify({'success': True, 'data': response_data}), 201
        except TradingServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Error interno del servidor',
            }), 500

    @app.route('/api/orders/<order_id>', methods=['DELETE'])
    @require_auth
    def cancel_order(order_id: str):
        """Cancela una orden específica."""
        try:
            trading_service.cancel_order(order_id, user=g.current_user)
            socketio.emit('order_cancelled', {'order_id': order_id})
            return jsonify({
                'success': True,
                'message': f'Orden {order_id} cancelada exitosamente',
            })
        except TradingServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/api/quote/<symbol>', methods=['GET'])
    @require_auth
    def get_quote(symbol: str):
        """Obtiene la cotización actual de un símbolo."""
        try:
            quote = alpaca_service.get_last_quote(symbol.upper(), user=g.current_user)
            return jsonify({'success': True, 'data': quote})
        except AlpacaServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/api/bars/<symbol>', methods=['GET'])
    @require_auth
    def get_bars(symbol: str):
        """Obtiene barras históricas de un símbolo."""
        try:
            timeframe = request.args.get('timeframe', '1D')
            limit = int(request.args.get('limit', 100))

            bars = alpaca_service.get_bars(
                symbol.upper(), timeframe, limit, user=g.current_user
            )
            return jsonify({'success': True, 'data': bars})
        except AlpacaServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Parámetro limit debe ser un número',
            }), 400

    @app.route('/api/chart-data/<symbol>', methods=['GET'])
    @require_auth
    def get_chart_data(symbol: str):
        """Obtiene datos combinados de barras e info de cotización para el gráfico principal."""
        try:
            timeframe = request.args.get('timeframe', '1D')
            limit = int(request.args.get('limit', 100))

            bars = alpaca_service.get_bars(
                symbol.upper(), timeframe, limit, user=g.current_user
            )
            quote = alpaca_service.get_last_quote(symbol.upper(), user=g.current_user)
            return jsonify({'success': True, 'data': {'bars': bars, 'quote': quote}})
        except AlpacaServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Parámetro limit debe ser un número',
            }), 400

    @app.route('/api/swing-scan', methods=['POST'])
    @require_auth
    def swing_scan():
        """Escanea tickers con la estrategia swing y opcionalmente ejecuta órdenes."""
        try:
            data = request.get_json(silent=True) or {}

            tickers = data.get('tickers')
            execute = bool(data.get('execute', False))

            if not tickers:
                tickers = ['AAPL', 'MSFT', 'AMZN', 'NVDA', 'META']

            if not isinstance(tickers, list) or not tickers:
                return jsonify({
                    'success': False,
                    'error': 'El campo tickers debe ser una lista no vacía',
                }), 400

            symbols: List[str] = [str(t).upper() for t in tickers]

            if execute:
                results = swing_strategy_service.scan_and_trade(
                    symbols, user=g.current_user
                )
            else:
                results = []
                for symbol in symbols:
                    signal = swing_strategy_service.generate_signal(
                        symbol, user=g.current_user
                    )
                    results.append({
                        'symbol': symbol,
                        'has_signal': signal.has_signal,
                        'entry_price': signal.entry_price,
                        'stop_price': signal.stop_price,
                        'take_profit_price': signal.take_profit_price,
                        'qty': signal.qty,
                        'reason': signal.reason,
                    })

            return jsonify({'success': True, 'data': results})
        except SwingStrategyServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Error interno del servidor',
            }), 500
