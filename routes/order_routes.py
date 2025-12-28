import logging
from flask import Blueprint, jsonify, request, g
from flask_socketio import SocketIO
from utils.auth_utils import require_auth
from services.trading_service import trading_service, TradingServiceException
from models.order import OrderSide

logger = logging.getLogger(__name__)

order_bp = Blueprint('order_bp', __name__)
_socketio = None

def init_order_socket(socketio: SocketIO):
    global _socketio
    _socketio = socketio

@order_bp.route('orders', methods=['GET'])
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

@order_bp.route('orders', methods=['POST'])
@require_auth
def create_order():
    """Crea una nueva orden."""
    try:
        data = request.get_json() or {}

        if 'symbol' not in data or 'side' not in data or 'order_type' not in data:
            return jsonify({
                'success': False,
                'error': 'Campos requeridos faltantes: symbol, side, order_type',
            }), 400

        if 'qty' not in data and 'notional' not in data:
            return jsonify({
                'success': False,
                'error': 'Se debe especificar qty o notional',
            }), 400

        qty = float(data['qty']) if 'qty' in data and data['qty'] else None
        notional = float(data['notional']) if 'notional' in data and data['notional'] else None

        side = (
            OrderSide.BUY
            if str(data['side']).lower() == 'buy'
            else OrderSide.SELL
        )

        if str(data['order_type']).lower() == 'market':
            order = trading_service.create_market_order(
                symbol=str(data['symbol']).upper(),
                qty=qty,
                notional=notional,
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
                qty=qty,
                notional=notional,
                side=side,
                limit_price=float(data['limit_price']),
                user=g.current_user,
            )
        elif str(data['order_type']).lower() == 'stop':
            if 'stop_price' not in data:
                return jsonify({
                    'success': False,
                    'error': 'stop_price requerido para orden stop',
                }), 400

            order = trading_service.create_stop_order(
                symbol=str(data['symbol']).upper(),
                qty=float(data['qty']),
                side=side,
                stop_price=float(data['stop_price']),
                user=g.current_user,
            )
        elif str(data['order_type']).lower() == 'stop_limit':
            if 'stop_price' not in data or 'limit_price' not in data:
                return jsonify({
                    'success': False,
                    'error': 'stop_price y limit_price requeridos para orden stop limit',
                }), 400

            order = trading_service.create_stop_limit_order(
                symbol=str(data['symbol']).upper(),
                qty=float(data['qty']),
                side=side,
                stop_price=float(data['stop_price']),
                limit_price=float(data['limit_price']),
                user=g.current_user,
            )
        elif str(data['order_type']).lower() == 'trailing_stop':
            if 'trail_price' not in data and 'trail_percent' not in data:
                return jsonify({
                    'success': False,
                    'error': 'trail_price o trail_percent requerido para trailing stop',
                }), 400

            order = trading_service.create_trailing_stop_order(
                symbol=str(data['symbol']).upper(),
                qty=float(data['qty']),
                side=side,
                trail_price=data.get('trail_price'),
                trail_percent=data.get('trail_percent'),
                user=g.current_user,
            )
        elif str(data['order_type']).lower() == 'bracket':
            required_bracket = ['limit_price', 'take_profit', 'stop_loss']
            for field in required_bracket:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f'{field} requerido para orden bracket',
                    }), 400

            limit_price = float(data['limit_price'])
            tp_limit_price = float(data['take_profit']['limit_price'])
            sl_stop_price = float(data['stop_loss']['stop_price'])
            
            # Validar lógica de precios según el lado de la orden
            if str(data['side']).lower() == 'buy':
                # Para compra: SL < entrada < TP
                if sl_stop_price >= limit_price:
                    return jsonify({
                        'success': False,
                        'error': f'Para compra, stop loss ({sl_stop_price}) debe ser menor al precio de entrada ({limit_price})',
                    }), 400
                
                if tp_limit_price <= limit_price:
                    return jsonify({
                        'success': False,
                        'error': f'Para compra, take profit ({tp_limit_price}) debe ser mayor al precio de entrada ({limit_price})',
                    }), 400
            else:
                # Para venta: TP < entrada < SL
                if tp_limit_price >= limit_price:
                    return jsonify({
                        'success': False,
                        'error': f'Para venta, take profit ({tp_limit_price}) debe ser menor al precio de entrada ({limit_price})',
                    }), 400
                
                if sl_stop_price <= limit_price:
                    return jsonify({
                        'success': False,
                        'error': f'Para venta, stop loss ({sl_stop_price}) debe ser mayor al precio de entrada ({limit_price})',
                    }), 400

            # Bracket order usa limit como tipo base con order_class BRACKET
            order = trading_service.create_bracket_order(
                symbol=str(data['symbol']).upper(),
                qty=float(data['qty']),
                side=side,
                limit_price=limit_price,
                take_profit=data['take_profit'],
                stop_loss=data['stop_loss'],
                user=g.current_user,
            )
        else:
            return jsonify({
                'success': False,
                'error': f"Tipo de orden no soportado: {data['order_type']}",
            }), 400

        logger.info(f"Orden enviada exitosamente: {order.order_id}")

        try:
            order_dict = order.to_dict()
            logger.info(f"Orden convertida a dict: {order_dict}")
            if _socketio:
                _socketio.emit('order_created', order_dict)
            return jsonify({
                'success': True, 
                'data': order_dict,
                'message': 'Orden creada exitosamente'
            }), 201
        except Exception as e:
            logger.error(f"Error al convertir orden a dict o emitir socket: {str(e)}")
            # Devolver respuesta básica sin socketio
            return jsonify({
                'success': True, 
                'message': 'Orden creada exitosamente',
                'data': {
                    'order_id': order.order_id,
                    'symbol': order.symbol,
                    'status': 'created',
                }
            }), 201
    except TradingServiceException as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception:
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor',
        }), 500

@order_bp.route('orders/<order_id>', methods=['DELETE'])
@require_auth
def cancel_order(order_id: str):
    """Cancela una orden específica."""
    try:
        trading_service.cancel_order(order_id, user=g.current_user)
        if _socketio:
            _socketio.emit('order_cancelled', {'order_id': order_id})
        return jsonify({
            'success': True,
            'message': f'Orden {order_id} cancelada exitosamente',
        })
    except TradingServiceException as e:
        return jsonify({'success': False, 'error': str(e)}), 400
