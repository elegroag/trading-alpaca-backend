"""
Servicio para interactuar con Alpaca API.

Implementa el patrón Repository y el principio de Inversión de Dependencias (DIP)
de SOLID, permitiendo abstraer la lógica de acceso a datos del broker.
"""

from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timedelta

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopOrderRequest,
    StopLimitOrderRequest,
    GetOrdersRequest,
)
from alpaca.trading.enums import OrderSide as AlpacaOrderSide, TimeInForce
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config import config
from models.order import Order, Position, Account, Quote, OrderSide, OrderType
from models.user import User
from utils.security import decrypt_text

# Configurar logger
logger = logging.getLogger(__name__)


class AlpacaServiceException(Exception):
    """Excepción personalizada para errores del servicio de Alpaca."""
    pass


class AlpacaService:
    """
    Servicio que encapsula toda la interacción con Alpaca API.

    Esta clase implementa el patrón Singleton para garantizar una única
    conexión con Alpaca API durante el ciclo de vida de la aplicación.
    """

    _instance = None

    def __new__(cls):
        """Implementación del patrón Singleton."""
        if cls._instance is None:
            cls._instance = super(AlpacaService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Inicializa el servicio de Alpaca."""
        if self._initialized:
            return

        try:
            paper = 'paper' in config.ALPACA_BASE_URL.lower()

            # Cliente de trading de alpaca-py
            self._trading_client = TradingClient(
                api_key=config.ALPACA_API_KEY or None,
                secret_key=config.ALPACA_SECRET_KEY or None,
                paper=paper,
            )

            # Cliente de datos de mercado de alpaca-py
            self._data_client = StockHistoricalDataClient(
                api_key=config.ALPACA_API_KEY or None,
                secret_key=config.ALPACA_SECRET_KEY or None,
            )

            logger.info("Alpaca API inicializada correctamente con alpaca-py")
            self._initialized = True
        except Exception as e:
            logger.error(f"Error al inicializar Alpaca API: {str(e)}")
            raise AlpacaServiceException(f"No se pudo inicializar Alpaca API: {str(e)}")

    def _get_trading_client_for_user(self, user: Optional[User]) -> TradingClient:
        if user and user.alpaca_api_key_enc and user.alpaca_secret_key_enc:
            try:
                api_key = decrypt_text(user.alpaca_api_key_enc)
                secret_key = decrypt_text(user.alpaca_secret_key_enc)
            except Exception as e:
                logger.error(f"Error al descifrar claves de Alpaca para usuario: {str(e)}")
                raise AlpacaServiceException("No se pudieron descifrar las claves de Alpaca del usuario")

            paper_flag = getattr(user, "paper_trading", None)
            if paper_flag is None:
                base_url = user.alpaca_base_url or config.ALPACA_BASE_URL
                paper_flag = "paper" in base_url.lower()

            return TradingClient(
                api_key=api_key or None,
                secret_key=secret_key or None,
                paper=bool(paper_flag),
            )

        return self._trading_client

    def _get_data_client_for_user(self, user: Optional[User]) -> StockHistoricalDataClient:
        if user and user.alpaca_api_key_enc and user.alpaca_secret_key_enc:
            try:
                api_key = decrypt_text(user.alpaca_api_key_enc)
                secret_key = decrypt_text(user.alpaca_secret_key_enc)
            except Exception as e:
                logger.error(f"Error al descifrar claves de Alpaca para usuario (datos): {str(e)}")
                raise AlpacaServiceException("No se pudieron descifrar las claves de Alpaca del usuario")

            return StockHistoricalDataClient(
                api_key=api_key or None,
                secret_key=secret_key or None,
            )

        return self._data_client

    # ========================================================================
    # MÉTODOS DE CUENTA
    # ========================================================================

    def get_account(self, user: Optional[User] = None) -> Account:
        """
        Obtiene la información de la cuenta.

        Returns:
            Account: Información de la cuenta

        Raises:
            AlpacaServiceException: Si hay un error al obtener la cuenta
        """
        try:
            client = self._get_trading_client_for_user(user)
            alpaca_account = client.get_account()
            return Account.from_alpaca_account(alpaca_account)
        except APIError as e:
            logger.error(f"Error API de Alpaca al obtener cuenta: {str(e)}")
            raise AlpacaServiceException(f"Error al obtener cuenta: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al obtener cuenta: {str(e)}")
            raise AlpacaServiceException(f"Error inesperado: {str(e)}")

    # ========================================================================
    # MÉTODOS DE POSICIONES
    # ========================================================================

    def get_positions(self, user: Optional[User] = None) -> List[Position]:
        """
        Obtiene todas las posiciones abiertas.

        Returns:
            List[Position]: Lista de posiciones abiertas

        Raises:
            AlpacaServiceException: Si hay un error al obtener posiciones
        """
        last_exception = None
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            try:
                client = self._get_trading_client_for_user(user)
                alpaca_positions = client.get_all_positions()
                if attempt > 1:
                    logger.info(
                        f"Posiciones obtenidas exitosamente en el intento {attempt}"
                    )
                return [
                    Position.from_alpaca_position(pos) for pos in alpaca_positions
                ]
            except APIError as e:
                logger.error(
                    f"Error API de Alpaca al obtener posiciones (intento {attempt}/{max_attempts}): {str(e)}"
                )
                last_exception = AlpacaServiceException(
                    f"Error al obtener posiciones: {str(e)}"
                )
                break
            except Exception as e:
                logger.error(
                    f"Error inesperado al obtener posiciones (intento {attempt}/{max_attempts}): {str(e)}"
                )
                last_exception = AlpacaServiceException(
                    f"Error inesperado: {str(e)}"
                )
                if attempt >= max_attempts:
                    break

        if last_exception is not None:
            raise last_exception

    def get_position(self, symbol: str, user: Optional[User] = None) -> Optional[Position]:
        """
        Obtiene una posición específica por símbolo.

        Args:
            symbol: Símbolo del activo

        Returns:
            Optional[Position]: Posición si existe, None si no

        Raises:
            AlpacaServiceException: Si hay un error al obtener la posición
        """
        try:
            client = self._get_trading_client_for_user(user)
            alpaca_position = client.get_open_position(symbol_or_asset_id=symbol)
            return Position.from_alpaca_position(alpaca_position)
        except APIError as e:
            if e.status_code == 404:
                return None
            logger.error(f"Error API de Alpaca al obtener posición {symbol}: {str(e)}")
            raise AlpacaServiceException(f"Error al obtener posición: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al obtener posición {symbol}: {str(e)}")
            raise AlpacaServiceException(f"Error inesperado: {str(e)}")

    # ========================================================================
    # MÉTODOS DE ÓRDENES
    # ========================================================================

    def submit_order_request(self, order_request, user: Optional[User] = None) -> Order:
        """
        Envía directamente un OrderRequest de Alpaca al broker.

        Args:
            order_request: OrderRequest de Alpaca (MarketOrderRequest, LimitOrderRequest, etc.)
            user: Usuario autenticado

        Returns:
            Order: Orden creada con ID asignado

        Raises:
            AlpacaServiceException: Si hay un error al enviar la orden
        """
        try:
            # Obtener cliente de trading para el usuario
            trading_client = self._get_trading_client_for_user(user)
            
            # Enviar orden directamente
            submitted_order = trading_client.submit_order(order_request)
            
            # Convertir a nuestro modelo Order
            order = Order(
                order_id=submitted_order.id,
                symbol=submitted_order.symbol,
                qty=submitted_order.qty,
                side=OrderSide.BUY if submitted_order.side.value == 'buy' else OrderSide.SELL,
                order_type=self._map_alpaca_order_type(submitted_order),
                time_in_force=submitted_order.time_in_force.value,
                limit_price=getattr(submitted_order, 'limit_price', None),
                stop_price=getattr(submitted_order, 'stop_price', None),
                status=submitted_order.status.value,
                created_at=submitted_order.created_at,
                filled_qty=getattr(submitted_order, 'filled_qty', None),
                filled_avg_price=getattr(submitted_order, 'filled_avg_price', None),
            )
            
            logger.info(f"Orden enviada exitosamente: {order.order_id}")
            return order
            
        except Exception as e:
            logger.error(f"Error inesperado al enviar orden: {str(e)}")
            raise AlpacaServiceException(f"Error inesperado: {str(e)}")

    def _map_alpaca_order_type(self, order) -> OrderType:
        """Mapea el tipo de orden de Alpaca a nuestro enum."""
        if hasattr(order, 'order_class') and order.order_class:
            if order.order_class.value == 'bracket':
                return OrderType.BRACKET
        
        # Mapeo por tipo de request
        order_type = type(order).__name__.replace('OrderRequest', '').upper()
        return getattr(OrderType, order_type, OrderType.MARKET)

    def submit_order(self, order: Order, user: Optional[User] = None) -> Order:
        """
        Envía una orden al broker.

        Args:
            order: Orden a enviar

        Returns:
            Order: Orden creada con ID asignado

        Raises:
            AlpacaServiceException: Si hay un error al enviar la orden
        """
        try:
            # Mapear lado de la orden
            alpaca_side = (
                AlpacaOrderSide.BUY
                if order.side == OrderSide.BUY
                else AlpacaOrderSide.SELL
            )

            # Mapear time in force
            try:
                alpaca_tif = getattr(TimeInForce, order.time_in_force.upper())
            except AttributeError:
                raise AlpacaServiceException(
                    f"Time in force no soportado: {order.time_in_force}"
                )

            # Preparar OrderRequest específico según el tipo de orden
            if order.order_type == OrderType.MARKET:
                order_data = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    notional=order.notional,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                )
            elif order.order_type == OrderType.LIMIT:
                if order.limit_price is None:
                    raise AlpacaServiceException(
                        "Precio límite requerido para orden límite"
                    )
                order_data = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    notional=order.notional,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                    limit_price=order.limit_price,
                )
            elif order.order_type == OrderType.STOP:
                if order.stop_price is None:
                    raise AlpacaServiceException(
                        "Precio stop requerido para orden stop"
                    )
                order_data = StopOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                    stop_price=order.stop_price,
                )
            elif order.order_type == OrderType.STOP_LIMIT:
                if order.limit_price is None or order.stop_price is None:
                    raise AlpacaServiceException(
                        "Precios límite y stop requeridos para orden stop limit"
                    )
                order_data = StopLimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                    limit_price=order.limit_price,
                    stop_price=order.stop_price,
                )
            else:
                raise AlpacaServiceException(
                    f"Tipo de orden no soportado: {order.order_type}"
                )

            # Enviar orden usando alpaca-py
            client = self._get_trading_client_for_user(user)
            alpaca_order = client.submit_order(order_data=order_data)

            # Retornar orden con información actualizada
            return Order.from_alpaca_order(alpaca_order)

        except APIError as e:
            logger.error(f"Error API de Alpaca al enviar orden: {str(e)}")
            raise AlpacaServiceException(f"Error al enviar orden: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al enviar orden: {str(e)}")
            raise AlpacaServiceException(f"Error inesperado: {str(e)}")

    def get_orders(self, status: str = 'open', user: Optional[User] = None) -> List[Order]:
        """
        Obtiene las órdenes según su estado.

        Args:
            status: Estado de las órdenes ('open', 'closed', 'all')

        Returns:
            List[Order]: Lista de órdenes

        Raises:
            AlpacaServiceException: Si hay un error al obtener órdenes
        """
        try:
            orders_filter = GetOrdersRequest(status=status) if status else None
            client = self._get_trading_client_for_user(user)
            alpaca_orders = client.get_orders(filter=orders_filter)
            orders = [Order.from_alpaca_order(order) for order in alpaca_orders]

            orders.sort(
                key=lambda o: (o.created_at or o.updated_at),
                reverse=True,
            )

            return orders
        except APIError as e:
            logger.error(f"Error API de Alpaca al obtener órdenes: {str(e)}")
            raise AlpacaServiceException(f"Error al obtener órdenes: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al obtener órdenes: {str(e)}")
            raise AlpacaServiceException(f"Error inesperado: {str(e)}")

    def cancel_order(self, order_id: str, user: Optional[User] = None) -> bool:
        """
        Cancela una orden específica.

        Args:
            order_id: ID de la orden a cancelar

        Returns:
            bool: True si se canceló exitosamente

        Raises:
            AlpacaServiceException: Si hay un error al cancelar la orden
        """
        try:
            client = self._get_trading_client_for_user(user)
            client.cancel_order_by_id(order_id)
            logger.info(f"Orden {order_id} cancelada exitosamente")
            return True
        except APIError as e:
            logger.error(f"Error API de Alpaca al cancelar orden {order_id}: {str(e)}")
            raise AlpacaServiceException(f"Error al cancelar orden: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al cancelar orden {order_id}: {str(e)}")
            raise AlpacaServiceException(f"Error inesperado: {str(e)}")

    def is_fractionable(self, symbol: str, user: Optional[User] = None) -> bool:
        """
        Verifica si un activo permite órdenes fraccionadas.

        Args:
            symbol: Símbolo del activo
            user: Usuario autenticado

        Returns:
            bool: True si el activo es fractionable, False en caso contrario
        """
        try:
            client = self._get_trading_client_for_user(user)
            asset = client.get_asset(symbol_or_asset_id=symbol)
            return getattr(asset, 'fractionable', False)
        except Exception as e:
            logger.error(f"Error al verificar si el activo {symbol} es fractionable: {str(e)}")
            return False

    def get_assets(self, asset_class: str = 'us_equity', exchange: Optional[str] = None, user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Obtiene activos filtrados por clase e intercambio.
        """
        try:
            from alpaca.trading.requests import GetAssetsRequest
            from alpaca.trading.enums import AssetClass
            
            client = self._get_trading_client_for_user(user)
            params = GetAssetsRequest(asset_class=AssetClass(asset_class))
            all_assets = client.get_all_assets(params)
            
            filtered = []
            for a in all_assets:
                if not a.tradable or a.status != 'active':
                    continue
                if exchange and a.exchange.value.upper() != exchange.upper():
                    continue
                
                filtered.append({
                    'symbol': a.symbol,
                    'name': a.name,
                    'exchange': a.exchange.value,
                    'fractionable': getattr(a, 'fractionable', False)
                })
            return filtered
        except Exception as e:
            logger.error(f"Error al obtener activos: {str(e)}")
            raise AlpacaServiceException(f"Error al obtener activos: {str(e)}")

    def get_snapshots(self, symbols: List[str], user: Optional[User] = None) -> Dict[str, Any]:
        """
        Obtiene snapshots (datos en tiempo real) para múltiples símbolos.
        """
        try:
            from alpaca.data.requests import StockSnapshotRequest
            
            data_client = self._get_data_client_for_user(user)
            request_params = StockSnapshotRequest(symbol_or_symbols=symbols)
            snapshots = data_client.get_stock_snapshot(request_params)
            
            result = {}
            for symbol, snp in snapshots.items():
                price = snp.latest_trade.price if snp.latest_trade else 0
                open_price = snp.daily_bar.open if snp.daily_bar else price
                daily_change_pct = ((price / open_price) - 1) * 100 if open_price > 0 else 0
                
                result[symbol] = {
                    'price': price,
                    'daily_change_pct': daily_change_pct,
                    'volume': snp.daily_bar.volume if snp.daily_bar else 0,
                    'timestamp': snp.latest_trade.timestamp.isoformat() if snp.latest_trade else None
                }
            return result
        except Exception as e:
            logger.error(f"Error al obtener snapshots: {str(e)}")
            raise AlpacaServiceException(f"Error al obtener snapshots: {str(e)}")

    # ========================================================================
    # MÉTODOS DE DATOS DE MERCADO
    # ========================================================================

    def get_last_quote(self, symbol: str, user: Optional[User] = None) -> Dict[str, Any]:
        """
        Obtiene la última cotización de un símbolo.

        Args:
            symbol: Símbolo del activo

        Returns:
            Dict[str, Any]: Cotización actual

        Raises:
            AlpacaServiceException: Si hay un error al obtener la cotización
        """
        try:
            request = StockLatestTradeRequest(symbol_or_symbols=symbol)
            data_client = self._get_data_client_for_user(user)
            latest_trade = data_client.get_stock_latest_trade(request)
            trade = latest_trade[symbol]

            asset_name = None
            asset_class_str = None
            asset_exchange_str = None
            asset_attributes: Optional[list[str]] = None
            try:
                client = self._get_trading_client_for_user(user)
                asset = client.get_asset(symbol_or_asset_id=symbol)
                asset_name = getattr(asset, "name", None)

                asset_class = getattr(asset, "asset_class", None)
                if asset_class is not None:
                    asset_class_str = (
                        asset_class.value
                        if hasattr(asset_class, "value")
                        else str(asset_class)
                    )

                asset_exchange = getattr(asset, "exchange", None)
                if asset_exchange is not None:
                    asset_exchange_str = (
                        asset_exchange.value
                        if hasattr(asset_exchange, "value")
                        else str(asset_exchange)
                    )

                attrs = getattr(asset, "attributes", None)
                if attrs is not None:
                    asset_attributes = [str(a) for a in list(attrs)]
            except Exception:
                # Si falla la obtención del asset, devolvemos solo la información básica de precio
                asset_name = asset_name

            close_price = None
            try:
                # Obtener las últimas 2 barras para usar el cierre del día anterior
                bars = self.get_bars(symbol, '1D', limit=2, user=user)
                if bars and len(bars) >= 2:
                    # Usar el cierre del día anterior (penúltima barra)
                    prev_bar = bars[-2]
                    close_value = prev_bar.get('close')
                    if close_value is not None:
                        close_price = float(close_value)
                elif bars and len(bars) == 1:
                    # Solo hay una barra, usar su cierre
                    last_bar = bars[-1]
                    close_value = last_bar.get('close')
                    if close_value is not None:
                        close_price = float(close_value)
            except Exception:
                close_price = None

            # Intentar obtener volumen y trade_count de la barra diaria del snapshot
            volume = None
            trade_count = None
            try:
                # Usamos snapshots para obtener datos más completos en una sola llamada
                request_snapshot = StockSnapshotRequest(symbol_or_symbols=symbol)
                snp_resp = data_client.get_stock_snapshot(request_snapshot)
                if symbol in snp_resp:
                    snp = snp_resp[symbol]
                    if snp.daily_bar:
                        volume = int(snp.daily_bar.volume)
                        trade_count = int(snp.daily_bar.trade_count) if snp.daily_bar.trade_count else None
            except Exception:
                pass

            return {
                'symbol': symbol,
                'price': float(trade.price),
                'close': close_price,
                'size': trade.size,
                'volume': volume,
                'trade_count': trade_count,
                'timestamp': trade.timestamp.isoformat() if trade.timestamp else None,
                'name': asset_name,
                'exchange': asset_exchange_str,
                'asset_class': asset_class_str,
                'asset_attributes': asset_attributes,
            }
        except APIError as e:
            logger.error(f"Error API de Alpaca al obtener cotización {symbol}: {str(e)}")
            raise AlpacaServiceException(f"Error al obtener cotización: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al obtener cotización {symbol}: {str(e)}")
            raise AlpacaServiceException(f"Error inesperado: {str(e)}")

    def get_multiple_quotes(self, symbols: List[str], user: Optional[User] = None) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene cotizaciones múltiples en lote para mejor rendimiento.

        Args:
            symbols: Lista de símbolos a consultar
            user: Usuario autenticado (para usar sus claves si existen)

        Returns:
            Dict[str, Dict[str, Any]]: Diccionario con cotizaciones por símbolo

        Raises:
            AlpacaServiceException: Si hay un error al obtener las cotizaciones
        """
        try:
            if not symbols:
                return {}

            # Dividir en chunks de 250 (límite recomendado por Alpaca)
            chunk_size = 250
            all_quotes = {}

            for i in range(0, len(symbols), chunk_size):
                chunk = symbols[i:i + chunk_size]
                
                try:
                    # Usar snapshots para obtener datos en lote
                    request = StockSnapshotRequest(symbol_or_symbols=chunk)
                    data_client = self._get_data_client_for_user(user)
                    snapshots = data_client.get_stock_snapshot(request)

                    # Procesar cada snapshot
                    for symbol, snapshot in snapshots.items():
                        try:
                            # Obtener información adicional del asset
                            asset_name = None
                            asset_exchange_str = None
                            asset_class_str = None
                            
                            try:
                                client = self._get_trading_client_for_user(user)
                                asset = client.get_asset(symbol_or_asset_id=symbol)
                                asset_name = getattr(asset, "name", None)
                                
                                asset_exchange = getattr(asset, "exchange", None)
                                if asset_exchange is not None:
                                    asset_exchange_str = (
                                        asset_exchange.value
                                        if hasattr(asset_exchange, "value")
                                        else str(asset_exchange)
                                    )
                                
                                asset_class = getattr(asset, "asset_class", None)
                                if asset_class is not None:
                                    asset_class_str = (
                                        asset_class.value
                                        if hasattr(asset_class, "value")
                                        else str(asset_class)
                                    )
                            except Exception:
                                # Si falla el asset, continuamos con datos básicos
                                pass

                            # Calcular precio de cierre desde daily_bar
                            close_price = None
                            if hasattr(snapshot, 'daily_bar') and snapshot.daily_bar:
                                close_price = float(snapshot.daily_bar.close)

                            all_quotes[symbol] = {
                                'symbol': symbol,
                                'price': float(snapshot.latest_trade.price) if snapshot.latest_trade else None,
                                'close': close_price,
                                'size': snapshot.latest_trade.size if snapshot.latest_trade else None,
                                'timestamp': snapshot.latest_trade.timestamp.isoformat() if snapshot.latest_trade and snapshot.latest_trade.timestamp else None,
                                'name': asset_name,
                                'exchange': asset_exchange_str,
                                'asset_class': asset_class_str,
                            }
                        except Exception as e:
                            logger.debug(f"Error procesando snapshot para {symbol}: {str(e)}")
                            continue

                except APIError as e:
                    logger.error(f"Error API de Alpaca al obtener snapshots chunk {i//chunk_size + 1}: {str(e)}")
                    # Continuar con el siguiente chunk en lugar de fallar completamente
                    continue
                except Exception as e:
                    logger.error(f"Error inesperado al obtener snapshots chunk {i//chunk_size + 1}: {str(e)}")
                    continue

            return all_quotes
        except Exception as e:
            logger.error(f"Error general al obtener múltiples cotizaciones: {str(e)}")
            raise AlpacaServiceException(f"Error al obtener múltiples cotizaciones: {str(e)}")

    def get_bars(self, symbol: str, timeframe: str = '1D', limit: int = 200, user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Obtiene barras históricas de un símbolo.

        Args:
            symbol: Símbolo del activo
            timeframe: Marco temporal ('1Min', '5Min', '1H', '1D')
            limit: Número de barras a obtener

        Returns:
            List[Dict[str, Any]]: Lista de barras históricas

        Raises:
            AlpacaServiceException: Si hay un error al obtener las barras
        """
        try:
            # Convertir string de timeframe a TimeFrame de alpaca-py
            tf_str = timeframe.upper()
            # Normalizar y acotar el límite solicitado por el cliente
            requested_limit = max(1, int(limit))

            if tf_str.endswith('MIN'):
                # Para 1Min, 5Min, 15Min, etc. usamos siempre el límite de barras intradía
                effective_limit = min(requested_limit, config.MAX_BARS_MIN)
                try:
                    amount = int(tf_str[:-3])
                except ValueError:
                    raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")
                if amount <= 0:
                    raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")
                tf_obj = TimeFrame(amount, TimeFrameUnit.Minute)
                total_minutes = amount * effective_limit
                # Aumentar ventana a 7 días para cubrir fines de semana largos y feriados
                min_window = timedelta(days=7)
                dynamic_window = timedelta(minutes=total_minutes * 3)
                window = max(min_window, dynamic_window)
                start = datetime.utcnow() - window
            elif tf_str.endswith('H'):
                effective_limit = min(requested_limit, config.MAX_BARS_HOUR)
                try:
                    amount = int(tf_str[:-1])
                except ValueError:
                    raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")
                if amount <= 0:
                    raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")
                tf_obj = TimeFrame(amount, TimeFrameUnit.Hour)
                total_hours = amount * effective_limit
                start = datetime.utcnow() - timedelta(hours=total_hours * 2)
            elif tf_str.endswith('D'):
                effective_limit = min(requested_limit, config.MAX_BARS_DAY)
                try:
                    amount = int(tf_str[:-1])
                except ValueError:
                    raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")
                if amount <= 0:
                    raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")
                tf_obj = TimeFrame(amount, TimeFrameUnit.Day)
                total_days = amount * effective_limit
                # Ventana de 10 días para asegurar barras diarias incluso tras periodos sin mercado
                start = datetime.utcnow() - timedelta(days=max(10, total_days * 3))
            elif tf_str.endswith('W'):
                effective_limit = min(requested_limit, config.MAX_BARS_DAY)
                try:
                    amount = int(tf_str[:-1])
                except ValueError:
                    raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")
                if amount <= 0:
                    raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")
                tf_obj = TimeFrame(amount, TimeFrameUnit.Week)
                total_weeks = amount * effective_limit
                start = datetime.utcnow() - timedelta(weeks=total_weeks * 2)
            elif tf_str.endswith('M'):
                effective_limit = min(requested_limit, config.MAX_BARS_DAY)
                try:
                    amount = int(tf_str[:-1])
                except ValueError:
                    raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")
                if amount <= 0:
                    raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")
                tf_obj = TimeFrame(amount, TimeFrameUnit.Month)
                total_months = amount * effective_limit
                approx_days = total_months * 31
                start = datetime.utcnow() - timedelta(days=approx_days * 2)
            else:
                raise AlpacaServiceException(f"Timeframe no soportado: {timeframe}")

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf_obj,
                start=start,
            )

            data_client = self._get_data_client_for_user(user)
            bars = data_client.get_stock_bars(request)

            # El cliente histórico devuelve un BarSet indexado por símbolo.
            # Puede no contener el símbolo si no hay datos en el rango solicitado.
            try:
                symbol_bars = list(bars[symbol])
            except KeyError:
                logger.warning(
                    "Alpaca no devolvió barras para %s (timeframe=%s, limit=%s)",
                    symbol,
                    timeframe,
                    effective_limit,
                )
                return []

            if not symbol_bars:
                logger.warning(
                    "Alpaca devolvió conjunto vacío de barras para %s (timeframe=%s, limit=%s)",
                    symbol,
                    timeframe,
                    effective_limit,
                )
                return []

            # Ordenar por timestamp ascendente y quedarnos con las últimas
            symbol_bars.sort(key=lambda b: b.timestamp)

            if len(symbol_bars) > effective_limit:
                symbol_bars = symbol_bars[-effective_limit:]

            bars_list: List[Dict[str, Any]] = []
            for bar in symbol_bars:
                bars_list.append({
                    'timestamp': bar.timestamp.isoformat(),
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume),
                    'trade_count': int(bar.trade_count) if bar.trade_count else None,
                    'vwap': float(bar.vwap) if bar.vwap else None,
                })

            return bars_list

        except APIError as e:
            logger.error(f"Error API de Alpaca al obtener barras {symbol}: {str(e)}")
            raise AlpacaServiceException(f"Error al obtener barras: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al obtener barras {symbol}: {str(e)}")
            raise AlpacaServiceException(f"Error inesperado: {str(e)}")


# Instancia global del servicio
alpaca_service = AlpacaService()
