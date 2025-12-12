"""
Controlador WebSocket - Eventos de comunicación en tiempo real.

Este módulo contiene los manejadores de eventos WebSocket
para la comunicación bidireccional con los clientes.
"""

from flask import request
from flask_socketio import emit
import logging

from services.trading_service import trading_service
from services.alpaca_service import alpaca_service

# Configurar logger
logger = logging.getLogger(__name__)


def register_websocket_handlers(socketio):
    """
    Registra los manejadores de eventos WebSocket.
    
    Args:
        socketio: Instancia de Flask-SocketIO
    """
    
    @socketio.on('connect')
    def handle_connect():
        """Maneja la conexión de un cliente WebSocket."""
        logger.info(f'Cliente conectado: {request.sid}')
        emit('connected', {'message': 'Conectado al servidor de trading'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Maneja la desconexión de un cliente WebSocket."""
        logger.info(f'Cliente desconectado: {request.sid}')

    @socketio.on('subscribe_symbol')
    def handle_subscribe_symbol(data):
        """
        Maneja la suscripción a actualizaciones de un símbolo.
        
        Args:
            data: {'symbol': 'AAPL'}
        """
        try:
            symbol = data.get('symbol', '').upper()
            if not symbol:
                emit('error', {'message': 'Símbolo requerido'})
                return
            
            logger.info(f'Cliente {request.sid} suscrito a {symbol}')
            emit('subscribed', {'symbol': symbol, 'message': f'Suscrito a {symbol}'})
            
            # Enviar cotización inicial
            quote = alpaca_service.get_last_quote(symbol)
            emit('quote_update', quote)
            
        except Exception as e:
            logger.error(f"Error en suscripción: {str(e)}")
            emit('error', {'message': str(e)})

    @socketio.on('request_account_update')
    def handle_account_update():
        """Envía actualización de la cuenta al cliente."""
        try:
            account = trading_service.get_account_info()
            emit('account_update', account.to_dict())
        except Exception as e:
            logger.error(f"Error al actualizar cuenta: {str(e)}")
            emit('error', {'message': str(e)})

    @socketio.on('request_positions_update')
    def handle_positions_update():
        """Envía actualización de posiciones al cliente."""
        try:
            positions = trading_service.get_positions()
            emit('positions_update', [pos.to_dict() for pos in positions])
        except Exception as e:
            logger.error(f"Error al actualizar posiciones: {str(e)}")
            emit('error', {'message': str(e)})

    @socketio.on('request_orders_update')
    def handle_orders_update():
        """Envía actualización de órdenes al cliente."""
        try:
            orders = trading_service.get_open_orders()
            emit('orders_update', [order.to_dict() for order in orders])
        except Exception as e:
            logger.error(f"Error al actualizar órdenes: {str(e)}")
            emit('error', {'message': str(e)})
