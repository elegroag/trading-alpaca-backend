"""
Controlador de Trading - Endpoints REST para operaciones de trading.

Este módulo contiene los blueprints de Flask para los endpoints
de la API REST relacionados con trading.
"""

from flask import Blueprint, request, jsonify
import logging

from services.trading_service import trading_service, TradingServiceException
from services.alpaca_service import alpaca_service, AlpacaServiceException
from models.order import OrderSide

# Configurar logger
logger = logging.getLogger(__name__)

# Crear Blueprint
trading_bp = Blueprint('trading', __name__, url_prefix='/api')


@trading_bp.route('/account', methods=['GET'])
def get_account():
    """Obtiene información de la cuenta."""
    try:
        account = trading_service.get_account_info()
        return jsonify({
            'success': True,
            'data': account.to_dict()
        })
    except TradingServiceException as e:
        logger.error(f"Error al obtener cuenta: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@trading_bp.route('/positions', methods=['GET'])
def get_positions():
    """Obtiene todas las posiciones abiertas."""
    try:
        positions = trading_service.get_positions()
        return jsonify({
            'success': True,
            'data': [pos.to_dict() for pos in positions]
        })
    except TradingServiceException as e:
        logger.error(f"Error al obtener posiciones: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@trading_bp.route('/orders', methods=['GET'])
def get_orders():
    """Obtiene órdenes abiertas."""
    try:
        orders = trading_service.get_open_orders()
        return jsonify({
            'success': True,
            'data': [order.to_dict() for order in orders]
        })
    except TradingServiceException as e:
        logger.error(f"Error al obtener órdenes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@trading_bp.route('/orders', methods=['POST'])
def create_order():
    """
    Crea una nueva orden.
    
    Request Body:
        {
            "symbol": "AAPL",
            "qty": 10,
            "side": "buy",
            "order_type": "limit",
            "limit_price": 150.00 (opcional)
        }
    """
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['symbol', 'qty', 'side', 'order_type']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Campo requerido faltante: {field}'
                }), 400
        
        # Convertir side a enum
        side = OrderSide.BUY if data['side'].lower() == 'buy' else OrderSide.SELL
        
        # Crear orden según tipo
        if data['order_type'].lower() == 'market':
            order = trading_service.create_market_order(
                symbol=data['symbol'].upper(),
                qty=float(data['qty']),
                side=side
            )
        elif data['order_type'].lower() == 'limit':
            if 'limit_price' not in data:
                return jsonify({
                    'success': False,
                    'error': 'limit_price requerido para orden límite'
                }), 400
            
            order = trading_service.create_limit_order(
                symbol=data['symbol'].upper(),
                qty=float(data['qty']),
                side=side,
                limit_price=float(data['limit_price'])
            )
        else:
            return jsonify({
                'success': False,
                'error': f'Tipo de orden no soportado: {data["order_type"]}'
            }), 400
        
        return jsonify({
            'success': True,
            'data': order.to_dict()
        }), 201
        
    except TradingServiceException as e:
        logger.error(f"Error al crear orden: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error inesperado al crear orden: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500


@trading_bp.route('/swing-trade', methods=['POST'])
def create_swing_trade():
    """
    Crea una operación swing trade completa.
    
    Request Body:
        {
            "symbol": "AAPL",
            "qty": 10,
            "entry_price": 150.00,
            "take_profit_price": 160.00,
            "stop_loss_price": 145.00
        }
    """
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['symbol', 'qty', 'entry_price', 'take_profit_price', 'stop_loss_price']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Campo requerido faltante: {field}'
                }), 400
        
        # Crear swing trade
        result = trading_service.create_swing_trade(
            symbol=data['symbol'].upper(),
            qty=float(data['qty']),
            entry_price=float(data['entry_price']),
            take_profit_price=float(data['take_profit_price']),
            stop_loss_price=float(data['stop_loss_price'])
        )
        
        # Preparar respuesta
        response_data = {
            'entry_order': result['entry'].to_dict(),
            'take_profit_target': result['take_profit_target'],
            'stop_loss_target': result['stop_loss_target']
        }
        
        return jsonify({
            'success': True,
            'data': response_data
        }), 201
        
    except TradingServiceException as e:
        logger.error(f"Error al crear swing trade: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error inesperado al crear swing trade: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500


@trading_bp.route('/orders/<order_id>', methods=['DELETE'])
def cancel_order(order_id):
    """Cancela una orden específica."""
    try:
        trading_service.cancel_order(order_id)
        return jsonify({
            'success': True,
            'message': f'Orden {order_id} cancelada exitosamente'
        })
    except TradingServiceException as e:
        logger.error(f"Error al cancelar orden: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@trading_bp.route('/quote/<symbol>', methods=['GET'])
def get_quote(symbol):
    """Obtiene la cotización actual de un símbolo."""
    try:
        quote = alpaca_service.get_last_quote(symbol.upper())
        return jsonify({
            'success': True,
            'data': quote
        })
    except AlpacaServiceException as e:
        logger.error(f"Error al obtener cotización: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@trading_bp.route('/bars/<symbol>', methods=['GET'])
def get_bars(symbol):
    """
    Obtiene barras históricas de un símbolo.
    
    Query Params:
        timeframe: Marco temporal (default: '1D')
        limit: Número de barras (default: 100)
    """
    try:
        timeframe = request.args.get('timeframe', '1D')
        limit = int(request.args.get('limit', 100))
        
        bars = alpaca_service.get_bars(symbol.upper(), timeframe, limit)
        return jsonify({
            'success': True,
            'data': bars
        })
    except AlpacaServiceException as e:
        logger.error(f"Error al obtener barras: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': 'Parámetro limit debe ser un número'
        }), 400
