"""
SwingBotService - Servicio de bot de trading con stream de datos en tiempo real.

Usa Alpaca StockDataStream para recibir precios y emitir actualizaciones via callback.
"""

import os
import threading
import logging
from typing import Dict, Callable, Optional, Any

from alpaca.trading.client import TradingClient
from alpaca.data.live import StockDataStream
from config import config
from models.user import User
from utils.security import decrypt_text

logger = logging.getLogger(__name__)


class SwingBotService:
    """
    Servicio de bot de trading que usa Alpaca StockDataStream 
    para recibir precios en tiempo real y emitir actualizaciones via callback.
    """
    
    def __init__(self):
        # Usar las mismas credenciales de Alpaca que alpaca_service
        paper = 'paper' in config.ALPACA_BASE_URL.lower()
        self._api_key = config.ALPACA_API_KEY or None
        self._api_secret = config.ALPACA_SECRET_KEY or None
        
        self._trading_client = TradingClient(
            api_key=self._api_key,
            secret_key=self._api_secret,
            paper=paper,
        )
        self._stream: Optional[StockDataStream] = None
        self._stream_thread: Optional[threading.Thread] = None
        
        # Símbolos actualmente suscritos y sus callbacks (stream global, si se usa)
        self._subscriptions: Dict[str, Dict[str, Callable[[dict], None]]] = {}
        self._lock = threading.Lock()
        self._running = False

        # Streams individuales por usuario (user_key) usando claves Alpaca del usuario
        # user_key suele ser el user.id en string
        self._user_streams: Dict[str, StockDataStream] = {}
        self._user_stream_threads: Dict[str, threading.Thread] = {}
        # Mapeo de subscriber_id -> callback y símbolo
        self._user_callbacks: Dict[str, Callable[[dict], None]] = {}
        self._user_symbols: Dict[str, str] = {}
        self._user_for_subscriber: Dict[str, str] = {}
        # Símbolos suscritos por stream de usuario
        self._user_stream_symbols: Dict[str, set[str]] = {}
        # Handler por stream de usuario
        self._user_stream_handlers: Dict[str, Callable[[Any], Any]] = {}
    
    def _create_stream(self) -> StockDataStream:
        """Crea una nueva instancia del stream de datos."""
        return StockDataStream(self._api_key, self._api_secret)
    
    def subscribe_symbol(
        self,
        symbol: str,
        on_price_update: Callable[[dict], None],
        subscriber_id: Optional[str] = None,
    ) -> None:
        """
        Suscribe a actualizaciones de precio de un símbolo.
        Inicia el stream si no está corriendo.
        
        Args:
            symbol: Símbolo del activo (ej: 'AAPL')
            on_price_update: Callback que recibe {'symbol': str, 'price': float, ...}
        """
        symbol = symbol.upper()

        if subscriber_id is None:
            subscriber_id = symbol
        
        with self._lock:
            first_for_symbol = symbol not in self._subscriptions
            if symbol not in self._subscriptions:
                self._subscriptions[symbol] = {}
            self._subscriptions[symbol][subscriber_id] = on_price_update
            
            if not self._running:
                self._start_stream()
            elif self._stream and first_for_symbol:
                # Agregar símbolo al stream existente
                self._stream.subscribe_bars(self._handle_bar, symbol)
        
        logger.info(f"Bot suscrito a {symbol}")
    
    def unsubscribe_symbol(self, symbol: str, subscriber_id: Optional[str] = None) -> None:
        """
        Cancela la suscripción a un símbolo.
        Detiene el stream si no hay más suscripciones.
        """
        symbol = symbol.upper()
        
        with self._lock:
            subs_for_symbol = self._subscriptions.get(symbol)
            if not subs_for_symbol:
                return

            should_unsubscribe_symbol = False

            if subscriber_id is None:
                should_unsubscribe_symbol = True
                del self._subscriptions[symbol]
            else:
                if subscriber_id in subs_for_symbol:
                    del subs_for_symbol[subscriber_id]
                    if not subs_for_symbol:
                        should_unsubscribe_symbol = True
                        del self._subscriptions[symbol]

            if self._stream and should_unsubscribe_symbol:
                try:
                    self._stream.unsubscribe_bars(symbol)
                except Exception as e:
                    logger.warning(f"Error al desuscribir {symbol}: {e}")
            
            logger.info(f"Bot desuscrito de {symbol} (subscriber={subscriber_id})")
            
            # Si no hay más suscripciones, detener el stream
            if not self._subscriptions and self._running:
                self._stop_stream()

    def subscribe_symbol_for_user(
        self,
        symbol: str,
        on_price_update: Callable[[dict], None],
        subscriber_id: str,
        user: Optional[User] = None,
    ) -> None:
        """Suscribe un símbolo para un usuario usando un único stream Alpaca por usuario.

        Args:
            symbol: Símbolo del activo (ej: 'AAPL').
            on_price_update: Callback a invocar con los datos de precio.
            subscriber_id: Identificador del suscriptor (normalmente el sid de Socket.IO).
            user: Usuario autenticado, para usar sus claves Alpaca si existen.
        """

        sym = (symbol or "").upper().strip()
        if not sym:
            return
        if not subscriber_id:
            subscriber_id = sym

        # Clave lógica para agrupar el stream por usuario
        user_key = None
        if user is not None and getattr(user, "id", None) is not None:
            user_key = str(user.id)
        else:
            # Fallback raro: si no hay user, agrupar por subscriber
            user_key = f"anon:{subscriber_id}"

        with self._lock:
            # Registrar callback y símbolo para este suscriptor
            self._user_callbacks[subscriber_id] = on_price_update
            self._user_symbols[subscriber_id] = sym
            self._user_for_subscriber[subscriber_id] = user_key

            # Obtener o crear stream por usuario
            stream = self._user_streams.get(user_key)

            if stream is None:
                api_key = self._api_key
                secret_key = self._api_secret
                if (
                    user
                    and getattr(user, "alpaca_api_key_enc", None)
                    and getattr(user, "alpaca_secret_key_enc", None)
                ):
                    try:
                        api_key = decrypt_text(user.alpaca_api_key_enc)
                        secret_key = decrypt_text(user.alpaca_secret_key_enc)
                    except Exception as e:  # pragma: no cover - defensivo
                        logger.error(
                            f"Error al descifrar claves de Alpaca para stream de usuario {user_key}: {str(e)}"
                        )

                stream = StockDataStream(api_key or None, secret_key or None)

                async def handler(bar: Any) -> None:
                    data = {
                        "symbol": bar.symbol,
                        "price": float(bar.close),
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "volume": int(bar.volume),
                        "timestamp": bar.timestamp.isoformat(),
                    }

                    sym_bar = bar.symbol.upper()

                    # Determinar qué suscriptores de este usuario y símbolo deben recibir la actualización
                    with self._lock:
                        targets = [
                            cb
                            for sid, cb in self._user_callbacks.items()
                            if self._user_for_subscriber.get(sid) == user_key
                            and self._user_symbols.get(sid) == sym_bar
                        ]

                    for cb in targets:
                        try:
                            cb(data)
                        except Exception as e:
                            logger.error(
                                f"Error en callback de precio para {sym_bar} (user_key={user_key}): {e}"
                            )

                # Inicializar estructuras del stream de usuario
                self._user_streams[user_key] = stream
                self._user_stream_symbols[user_key] = set()
                self._user_stream_handlers[user_key] = handler

                # Suscribir primer símbolo
                stream.subscribe_bars(handler, sym)
                self._user_stream_symbols[user_key].add(sym)

                # Lanzar hilo para este stream de usuario
                def run_stream_for_user(key: str, s: StockDataStream) -> None:
                    try:
                        s.run()
                    except Exception as e:
                        logger.error(
                            f"Error en stream Alpaca para usuario {key}: {e}"
                        )
                    finally:
                        with self._lock:
                            self._user_streams.pop(key, None)
                            self._user_stream_threads.pop(key, None)
                            self._user_stream_handlers.pop(key, None)
                            self._user_stream_symbols.pop(key, None)

                            # Limpiar suscriptores asociados a este usuario
                            to_remove = [
                                sid
                                for sid, ukey in self._user_for_subscriber.items()
                                if ukey == key
                            ]
                            for sid in to_remove:
                                self._user_callbacks.pop(sid, None)
                                self._user_symbols.pop(sid, None)
                                self._user_for_subscriber.pop(sid, None)

                thread = threading.Thread(
                    target=run_stream_for_user, args=(user_key, stream), daemon=True
                )
                self._user_stream_threads[user_key] = thread
                thread.start()

                logger.info(
                    f"Stream Alpaca (usuario) iniciado para usuario {user_key}, símbolo {sym}"
                )
            else:
                # Stream ya existe para este usuario: solo suscribir el nuevo símbolo si no estaba
                handler = self._user_stream_handlers.get(user_key)
                symbols = self._user_stream_symbols.setdefault(user_key, set())
                if sym not in symbols:
                    stream.subscribe_bars(handler, sym)
                    symbols.add(sym)

                logger.info(
                    f"Stream Alpaca (usuario) reutilizado para usuario {user_key}, símbolo {sym}"
                )

    def unsubscribe_symbol_for_user(self, symbol: str, subscriber_id: str) -> None:
        """Desuscribe un símbolo para un suscriptor dentro del stream por usuario.

        Si ya no quedan suscriptores para ese símbolo, se desuscribe del stream Alpaca.
        Si ya no quedan suscriptores para ese usuario, se detiene el stream del usuario.
        """

        sym = (symbol or "").upper().strip()
        if not subscriber_id:
            return

        with self._lock:
            user_key = self._user_for_subscriber.get(subscriber_id)
            if not user_key:
                return

            # Eliminar mapeos de este suscriptor
            self._user_callbacks.pop(subscriber_id, None)
            self._user_symbols.pop(subscriber_id, None)
            self._user_for_subscriber.pop(subscriber_id, None)

            stream = self._user_streams.get(user_key)
            if stream is None:
                return

            # ¿Quedan otros suscriptores de este usuario para este símbolo?
            still_has_symbol = any(
                ukey == user_key and self._user_symbols.get(sid) == sym
                for sid, ukey in self._user_for_subscriber.items()
            )

            symbols = self._user_stream_symbols.get(user_key)
            if symbols is not None and sym in symbols and not still_has_symbol:
                try:
                    stream.unsubscribe_bars(sym)
                except Exception as e:
                    logger.warning(
                        f"Error al desuscribir símbolo {sym} del stream de usuario {user_key}: {e}"
                    )
                symbols.remove(sym)

            # ¿Quedan suscriptores para este usuario?
            has_any_subscriber = any(
                ukey == user_key for ukey in self._user_for_subscriber.values()
            )

            if not has_any_subscriber:
                try:
                    stream.stop()
                except Exception as e:
                    logger.warning(
                        f"Error al detener stream Alpaca para usuario {user_key}: {e}"
                    )

                self._user_streams.pop(user_key, None)
                self._user_stream_threads.pop(user_key, None)
                self._user_stream_handlers.pop(user_key, None)
                self._user_stream_symbols.pop(user_key, None)

                logger.info(
                    f"Stream Alpaca (usuario) detenido para usuario {user_key}, símbolo {sym}"
                )
    
    def unsubscribe_all(self) -> None:
        """Cancela todas las suscripciones y detiene el stream."""
        with self._lock:
            self._subscriptions.clear()
            self._stop_stream()
        
        logger.info("Bot: todas las suscripciones canceladas")
    
    def _start_stream(self) -> None:
        """Inicia el stream de datos en un hilo separado."""
        if self._running:
            return
        
        self._stream = self._create_stream()
        
        # Suscribir a todos los símbolos actuales
        symbols = list(self._subscriptions.keys())
        if symbols:
            self._stream.subscribe_bars(self._handle_bar, *symbols)
        
        self._running = True
        self._stream_thread = threading.Thread(target=self._run_stream, daemon=True)
        self._stream_thread.start()
        
        logger.info(f"Stream iniciado para símbolos: {symbols}")
    
    def _stop_stream(self) -> None:
        """Detiene el stream de datos."""
        if not self._running:
            return
        
        self._running = False
        
        if self._stream:
            try:
                self._stream.stop()
            except Exception as e:
                logger.warning(f"Error al detener stream: {e}")
            self._stream = None
        
        logger.info("Stream detenido")
    
    def _run_stream(self) -> None:
        """Ejecuta el stream (bloqueante, corre en hilo separado)."""
        try:
            if self._stream:
                self._stream.run()
        except Exception as e:
            logger.error(f"Error en stream: {e}")
            self._running = False
    
    async def _handle_bar(self, bar: Any) -> None:
        """
        Handler para barras recibidas del stream.
        Llama al callback correspondiente con los datos del precio.
        """
        symbol = bar.symbol
        
        with self._lock:
            callbacks = list(self._subscriptions.get(symbol, {}).values())
        
        if not callbacks:
            return

        data = {
            'symbol': symbol,
            'price': float(bar.close),
            'open': float(bar.open),
            'high': float(bar.high),
            'low': float(bar.low),
            'volume': int(bar.volume),
            'timestamp': bar.timestamp.isoformat()
        }

        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error en callback para {symbol}: {e}")
    
    def get_positions(self) -> list:
        """Obtiene todas las posiciones abiertas."""
        try:
            positions = self._trading_client.get_all_positions()
            return [
                {
                    'symbol': p.symbol,
                    'qty': float(p.qty),
                    'avg_entry_price': float(p.avg_entry_price),
                    'current_price': float(p.current_price),
                    'market_value': float(p.market_value),
                    'unrealized_pl': float(p.unrealized_pl),
                    'unrealized_plpc': float(p.unrealized_plpc) * 100,
                    'side': p.side.value if hasattr(p.side, 'value') else str(p.side)
                }
                for p in positions
            ]
        except Exception as e:
            logger.error(f"Error obteniendo posiciones: {e}")
            return []
    
    def get_position(self, symbol: str) -> Optional[dict]:
        """Obtiene la posición de un símbolo específico."""
        try:
            p = self._trading_client.get_open_position(symbol.upper())
            return {
                'symbol': p.symbol,
                'qty': float(p.qty),
                'avg_entry_price': float(p.avg_entry_price),
                'current_price': float(p.current_price),
                'market_value': float(p.market_value),
                'unrealized_pl': float(p.unrealized_pl),
                'unrealized_plpc': float(p.unrealized_plpc) * 100,
                'side': p.side.value if hasattr(p.side, 'value') else str(p.side)
            }
        except Exception:
            return None
    
    @property
    def is_running(self) -> bool:
        """Indica si el stream está corriendo."""
        return self._running
    
    @property
    def subscribed_symbols(self) -> list:
        """Lista de símbolos actualmente suscritos."""
        with self._lock:
            return list(self._subscriptions.keys())


# Instancia singleton
swing_bot_service = SwingBotService()
