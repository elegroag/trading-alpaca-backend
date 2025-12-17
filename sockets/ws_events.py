"""Manejadores de eventos WebSocket para Trading Swing.

Registra los eventos de Socket.IO y coordina streams Alpaca por usuario,
actualizaciones de cuenta/posiciones y auto-trading swing.
"""

from datetime import datetime
import logging
from time import sleep
from typing import Dict, Optional

from flask import request
from flask_socketio import SocketIO, emit, disconnect

from config import config
from models.user import User, get_user_by_id
from utils.security import decode_jwt
from services.trading_service import trading_service
from services.alpaca_service import alpaca_service
from services.swing_strategy_service import (
    swing_strategy_service,
    SwingStrategyServiceException,
)
from services.swing_bot_service import swing_bot_service

logger = logging.getLogger(__name__)


SWING_AUTOTRADE_ENABLED = config.SWING_AUTOTRADE_ENABLED
auto_swing_state: Dict[str, str] = {}


def register_socket_handlers(socketio: SocketIO) -> None:
    """Registra los manejadores de eventos WebSocket sobre una instancia de SocketIO."""

    # Diccionario para rastrear suscripciones por cliente (sid -> symbol)
    client_subscriptions: Dict[str, str] = {}

    # Diccionario para rastrear usuarios autenticados por cliente (sid -> User)
    ws_clients: Dict[str, User] = {}

    def _get_ws_user() -> Optional[User]:
        sid = request.sid
        return ws_clients.get(sid)

    def _maybe_auto_swing_trade(user: User, symbol: str, sid: str) -> None:
        """Intenta ejecutar una operación swing automática para un usuario y símbolo.

        - Usa la cuenta Alpaca del usuario.
        - Solo ejecuta como máximo 1 vez por día por (usuario, símbolo).
        - No ejecuta si ya hay posición abierta en ese símbolo.
        """

        if not SWING_AUTOTRADE_ENABLED:
            return

        sym = (symbol or "").upper().strip()
        if not sym:
            return

        key = f"{user.id}:{sym}"
        today = datetime.utcnow().date().isoformat()

        last = auto_swing_state.get(key)
        if last == today:
            # Ya se ejecutó auto-swing para este símbolo y usuario hoy
            return

        try:
            # No abrir nueva operación si ya hay posición en el símbolo
            try:
                positions = trading_service.get_positions(user=user)
                for pos in positions:
                    if pos.symbol.upper() == sym and float(pos.qty) > 0:
                        return
            except Exception as e:  # pragma: no cover - defensivo
                logger.error(
                    f"Auto-swing: error al obtener posiciones para {sym}: {str(e)}"
                )
                return

            try:
                signal = swing_strategy_service.generate_signal(sym, user=user)
            except SwingStrategyServiceException as e:
                logger.error(
                    f"Auto-swing: error al generar señal para {sym}: {str(e)}"
                )
                return

            if not signal.has_signal or not signal.qty or signal.qty <= 0:
                return

            try:
                order = swing_strategy_service.execute_signal(signal, user=user)
            except SwingStrategyServiceException as e:
                logger.error(
                    f"Auto-swing: error al ejecutar señal para {sym}: {str(e)}"
                )
                return

            order_id = getattr(order, "id", None)
            if order_id is not None:
                order_id = str(order_id)

            status = getattr(order, "status", None)
            if status is not None:
                status = str(status)

            auto_swing_state[key] = today

            payload = {
                "symbol": sym,
                "qty": signal.qty,
                "entry_price": signal.entry_price,
                "stop_price": signal.stop_price,
                "take_profit_price": signal.take_profit_price,
                "order_id": order_id,
                "status": status,
            }
            socketio.emit("swing_auto_trade", payload, room=sid)

        except Exception as e:  # pragma: no cover - defensivo
            logger.error(f"Auto-swing: error inesperado para {sym}: {str(e)}")

    @socketio.on('connect')
    def handle_connect() -> None:
        """Maneja la conexión de un cliente WebSocket."""
        logger.info('Cliente conectado: %s', request.sid)
        emit('connected', {'message': 'Conectado al servidor de trading'})

    @socketio.on('authenticate')
    def handle_authenticate(data):
        payload = data or {}
        token = payload.get('token')

        if not token:
            emit('error', {'message': 'Token requerido para autenticación WebSocket'})
            disconnect()
            return

        try:
            jwt_payload = decode_jwt(token)
        except Exception:
            emit('error', {'message': 'Token inválido o expirado'})
            disconnect()
            return

        user_id = jwt_payload.get('sub')
        if not user_id:
            emit('error', {'message': 'Token inválido'})
            disconnect()
            return

        user = get_user_by_id(user_id)
        if not user:
            emit('error', {'message': 'Usuario no encontrado'})
            disconnect()
            return

        ws_clients[request.sid] = user
        emit('authenticated', {'user': user.to_dict()})

    @socketio.on('disconnect')
    def handle_disconnect() -> None:
        """Maneja la desconexión de un cliente WebSocket."""
        sid = request.sid
        logger.info('Cliente desconectado: %s', sid)

        # Desuscribir del bot si tenía una suscripción activa
        if sid in client_subscriptions:
            symbol = client_subscriptions[sid]
            swing_bot_service.unsubscribe_symbol_for_user(symbol, subscriber_id=sid)
            del client_subscriptions[sid]
            logger.info('Bot detenido para %s (cliente %s desconectado)', symbol, sid)

        # Eliminar usuario autenticado asociado a este cliente
        ws_clients.pop(sid, None)

    @socketio.on('subscribe_symbol')
    def handle_subscribe_symbol(data):
        """Maneja la suscripción a actualizaciones de un símbolo.

        Args:
            data: {'symbol': 'AAPL'}
        """
        try:
            user = _get_ws_user()
            if not user:
                emit('error', {'message': 'Autenticación requerida'})
                disconnect()
                return

            symbol = str(data.get('symbol', '')).upper()
            if not symbol:
                emit('error', {'message': 'Símbolo requerido'})
                return

            sid = request.sid

            # Si el cliente ya estaba suscrito a otro símbolo, desuscribir
            if sid in client_subscriptions:
                old_symbol = client_subscriptions[sid]
                if old_symbol != symbol:
                    swing_bot_service.unsubscribe_symbol(old_symbol, subscriber_id=sid)
                    logger.info('Cliente %s cambió de %s a %s', sid, old_symbol, symbol)

            # Registrar nueva suscripción
            client_subscriptions[sid] = symbol

            logger.info('Cliente %s suscrito a %s', sid, symbol)
            emit('subscribed', {'symbol': symbol, 'message': f'Suscrito a {symbol}'})

            # Enviar cotización inicial
            quote = alpaca_service.get_last_quote(symbol, user=user)
            emit('quote_update', quote)

            # Enviar posición inicial del usuario si existe
            try:
                positions = trading_service.get_positions(user=user)
                for pos in positions:
                    if pos.symbol.upper() == symbol:
                        emit('position_update', pos.to_dict())
                        break
            except Exception as e:  # pragma: no cover - defensivo
                logger.error(
                    'Error al obtener posición inicial para %s: %s', symbol, str(e)
                )

            # Callback para emitir actualizaciones de precio via SocketIO
            def on_price_update(price_data: dict) -> None:
                socketio.emit('quote_update', price_data, room=sid)

                user_for_sid = ws_clients.get(sid)
                if not user_for_sid:
                    return

                try:
                    positions_ws = trading_service.get_positions(user=user_for_sid)
                    symbol_ws = str(price_data.get('symbol', '')).upper()
                    for pos_ws in positions_ws:
                        if pos_ws.symbol.upper() == symbol_ws:
                            socketio.emit(
                                'position_update', pos_ws.to_dict(), room=sid
                            )
                            break
                except Exception as e:  # pragma: no cover - defensivo
                    logger.error(
                        'Error al obtener posición en actualización de precio para %s: %s',
                        symbol,
                        str(e),
                    )

                # Intentar auto-trading swing para este usuario y símbolo
                try:
                    _maybe_auto_swing_trade(user_for_sid, symbol_ws, sid)
                except Exception as e:  # pragma: no cover - defensivo
                    logger.error('Error en auto-swing para %s: %s', symbol_ws, str(e))

            # Iniciar stream Alpaca dedicado para este usuario y símbolo
            swing_bot_service.subscribe_symbol_for_user(
                symbol, on_price_update, subscriber_id=sid, user=user
            )

        except Exception as e:  # pragma: no cover - defensivo
            logger.error('Error en suscripción: %s', str(e))
            emit('error', {'message': str(e)})

    @socketio.on('unsubscribe_symbol')
    def handle_unsubscribe_symbol(data):
        """Maneja la desuscripción de un símbolo."""
        try:
            symbol = str(data.get('symbol', '')).upper()
            sid = request.sid

            if sid in client_subscriptions:
                del client_subscriptions[sid]

            if symbol:
                swing_bot_service.unsubscribe_symbol_for_user(symbol, subscriber_id=sid)
                logger.info('Cliente %s desuscrito de %s', sid, symbol)
                emit('unsubscribed', {'symbol': symbol})

        except Exception as e:  # pragma: no cover - defensivo
            logger.error('Error en desuscripción: %s', str(e))
            emit('error', {'message': str(e)})

    @socketio.on('request_account_update')
    def handle_account_update() -> None:
        """Envía actualización de la cuenta al cliente."""
        try:
            user = _get_ws_user()
            if not user:
                emit('error', {'message': 'Autenticación requerida'})
                disconnect()
                return

            account = trading_service.get_account_info(user=user)
            emit('account_update', account.to_dict())
        except Exception as e:  # pragma: no cover - defensivo
            logger.error('Error al actualizar cuenta: %s', str(e))
            emit('error', {'message': str(e)})

    @socketio.on('request_positions_update')
    def handle_positions_update() -> None:
        """Envía actualización de posiciones al cliente."""
        try:
            user = _get_ws_user()
            if not user:
                emit('error', {'message': 'Autenticación requerida'})
                disconnect()
                return

            positions = trading_service.get_positions(user=user)
            emit('positions_update', [pos.to_dict() for pos in positions])
        except Exception as e:  # pragma: no cover - defensivo
            logger.error('Error al actualizar posiciones: %s', str(e))
            emit('error', {'message': str(e)})
