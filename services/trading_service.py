"""
Servicio de lógica de negocio para operaciones de trading.

Implementa el patrón Service Layer y el principio de Responsabilidad Única (SRP),
separando la lógica de trading de la comunicación con el broker.
"""

from typing import List, Dict, Any, Optional
import logging
from models.order import Order, OrderSide, OrderType, Position, Account
from services.alpaca_service import alpaca_service, AlpacaServiceException
from models.user import User
from config import config

# Imports de Alpaca para nuevos tipos de órdenes
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopOrderRequest,
    StopLimitOrderRequest,
    TrailingStopOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
)
from alpaca.trading.enums import (
    OrderSide as AlpacaOrderSide,
    TimeInForce,
    OrderClass,
)

# Configurar logger
logger = logging.getLogger(__name__)


class TradingServiceException(Exception):
    """Excepción personalizada para errores del servicio de trading."""
    pass


class TradingService:
    """
    Servicio que encapsula la lógica de negocio para operaciones de trading.
    
    Proporciona métodos de alto nivel para crear órdenes con validaciones
    y cálculos de límites de compra/venta.
    """
    
    def __init__(self):
        """Inicializa el servicio de trading."""
        self._alpaca_service = alpaca_service
    
    # ========================================================================
    # VALIDACIONES
    # ========================================================================
    
    def _validate_order_size(self, symbol: str, qty: float, price: float) -> None:
        """
        Valida que el tamaño de la orden esté dentro de los límites.
        
        Args:
            symbol: Símbolo del activo
            qty: Cantidad de acciones
            price: Precio por acción
            
        Raises:
            TradingServiceException: Si la orden no cumple con los límites
        """
        order_value = qty * price
        
        if order_value < config.MIN_ORDER_SIZE:
            raise TradingServiceException(
                f"El valor de la orden (${order_value:.2f}) es menor al mínimo permitido (${config.MIN_ORDER_SIZE})"
            )
        
        if order_value > config.MAX_ORDER_SIZE:
            raise TradingServiceException(
                f"El valor de la orden (${order_value:.2f}) excede el máximo permitido (${config.MAX_ORDER_SIZE})"
            )
    
    def _validate_buying_power(self, order_value: float, user: Optional[User] = None) -> None:
        """
        Valida que haya suficiente poder de compra para la orden.
        
        Args:
            order_value: Valor total de la orden
            
        Raises:
            TradingServiceException: Si no hay suficiente poder de compra
        """
        try:
            account = self._alpaca_service.get_account(user=user)
            
            if order_value > account.buying_power:
                raise TradingServiceException(
                    f"Poder de compra insuficiente. Disponible: ${account.buying_power:.2f}, Requerido: ${order_value:.2f}"
                )
        except AlpacaServiceException as e:
            raise TradingServiceException(f"Error al validar poder de compra: {str(e)}")
    
    # ========================================================================
    # CREACIÓN DE ÓRDENES
    # ========================================================================
    
    def create_market_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        user: Optional[User] = None,
    ) -> Order:
        """
        Crea una orden de mercado.
        
        Args:
            symbol: Símbolo del activo
            qty: Cantidad de acciones
            side: Lado de la orden (compra/venta)
            
        Returns:
            Order: Orden creada
            
        Raises:
            TradingServiceException: Si hay un error al crear la orden
        """
        try:
            # Obtener precio actual para validaciones
            quote = self._alpaca_service.get_last_quote(symbol, user=user)
            current_price = quote['price']
            
            # Validar tamaño de orden
            self._validate_order_size(symbol, qty, current_price)
            
            # Validar poder de compra solo para órdenes de compra
            if side == OrderSide.BUY:
                self._validate_buying_power(qty * current_price, user=user)
            
            # Crear orden
            order = Order(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type=OrderType.MARKET,
                time_in_force='gtc'
            )
            
            # Enviar orden
            created_order = self._alpaca_service.submit_order(order, user=user)
            logger.info(f"Orden de mercado creada: {created_order.order_id}")
            
            return created_order
            
        except AlpacaServiceException as e:
            logger.error(f"Error de Alpaca al crear orden de mercado: {str(e)}")
            raise TradingServiceException(f"Error al crear orden: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear orden de mercado: {str(e)}")
            raise TradingServiceException(f"Error inesperado: {str(e)}")
    
    def create_limit_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        limit_price: float,
        user: Optional[User] = None,
    ) -> Order:
        """
        Crea una orden límite.
        
        Args:
            symbol: Símbolo del activo
            qty: Cantidad de acciones
            side: Lado de la orden (compra/venta)
            limit_price: Precio límite
            
        Returns:
            Order: Orden creada
            
        Raises:
            TradingServiceException: Si hay un error al crear la orden
        """
        try:
            # Validar tamaño de orden
            self._validate_order_size(symbol, qty, limit_price)
            
            # Validar poder de compra solo para órdenes de compra
            if side == OrderSide.BUY:
                self._validate_buying_power(qty * limit_price, user=user)
            
            # Crear orden
            order = Order(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type=OrderType.LIMIT,
                limit_price=limit_price,
                time_in_force='gtc'
            )
            
            # Enviar orden
            created_order = self._alpaca_service.submit_order(order)
            logger.info(f"Orden límite creada: {created_order.order_id}")
            
            return created_order
            
        except AlpacaServiceException as e:
            logger.error(f"Error de Alpaca al crear orden límite: {str(e)}")
            raise TradingServiceException(f"Error al crear orden: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear orden límite: {str(e)}")
            raise TradingServiceException(f"Error inesperado: {str(e)}")
    
    def create_swing_trade(
        self,
        symbol: str,
        qty: float,
        entry_price: float,
        take_profit_price: float,
        stop_loss_price: float,
        user: Optional[User] = None,
    ) -> Dict[str, Order]:
        """
        Crea una operación swing trade completa con entrada, take profit y stop loss.
        
        Args:
            symbol: Símbolo del activo
            qty: Cantidad de acciones
            entry_price: Precio de entrada (límite)
            take_profit_price: Precio objetivo (límite de venta)
            stop_loss_price: Precio de stop loss
            
        Returns:
            Dict[str, Order]: Diccionario con las órdenes creadas
            
        Raises:
            TradingServiceException: Si hay un error al crear las órdenes
        """
        try:
            # Validar lógica de precios
            if entry_price <= 0 or take_profit_price <= 0 or stop_loss_price <= 0:
                raise TradingServiceException("Los precios deben ser mayores a cero")
            
            if take_profit_price <= entry_price:
                raise TradingServiceException(
                    "El precio de take profit debe ser mayor al precio de entrada"
                )
            
            if stop_loss_price >= entry_price:
                raise TradingServiceException(
                    "El precio de stop loss debe ser menor al precio de entrada"
                )
            
            # Crear orden de entrada (límite de compra)
            entry_order = self.create_limit_order(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                limit_price=entry_price,
                user=user,
            )
            
            logger.info(f"Swing trade creado para {symbol}: Entry={entry_price}, TP={take_profit_price}, SL={stop_loss_price}")
            
            return {
                'entry': entry_order,
                'take_profit_target': take_profit_price,
                'stop_loss_target': stop_loss_price
            }
            
        except TradingServiceException:
            raise
        except Exception as e:
            logger.error(f"Error inesperado al crear swing trade: {str(e)}")
            raise TradingServiceException(f"Error inesperado: {str(e)}")
    
    def create_stop_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        stop_price: float,
        user: Optional[User] = None,
    ) -> Order:
        """
        Crea una orden stop.
        
        Args:
            symbol: Símbolo del activo
            qty: Cantidad de acciones
            side: Lado de la orden (buy/sell)
            stop_price: Precio de activación
            
        Returns:
            Order: Orden creada
            
        Raises:
            TradingServiceException: Si hay un error al crear la orden
        """
        try:
            if qty <= 0:
                raise TradingServiceException("La cantidad debe ser mayor a cero")
            
            if stop_price <= 0:
                raise TradingServiceException("El precio de stop debe ser mayor a cero")
            
            # Crear orden stop con Alpaca
            order_request = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                stop_price=stop_price,
            )
            
            order = self._alpaca_service.submit_order_request(order_request, user=user)
            
            logger.info(f"Orden stop creada: {symbol} {side} {qty} @ stop {stop_price}")
            return order
            
        except AlpacaServiceException as e:
            logger.error(f"Error al crear orden stop: {str(e)}")
            raise TradingServiceException(f"Error al crear orden stop: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear orden stop: {str(e)}")
            raise TradingServiceException(f"Error inesperado: {str(e)}")
    
    def create_stop_limit_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        stop_price: float,
        limit_price: float,
        user: Optional[User] = None,
    ) -> Order:
        """
        Crea una orden stop limit.
        
        Args:
            symbol: Símbolo del activo
            qty: Cantidad de acciones
            side: Lado de la orden (buy/sell)
            stop_price: Precio de activación
            limit_price: Precio límite
            
        Returns:
            Order: Orden creada
            
        Raises:
            TradingServiceException: Si hay un error al crear la orden
        """
        try:
            if qty <= 0:
                raise TradingServiceException("La cantidad debe ser mayor a cero")
            
            if stop_price <= 0:
                raise TradingServiceException("El precio de stop debe ser mayor a cero")
            
            if limit_price <= 0:
                raise TradingServiceException("El precio límite debe ser mayor a cero")
            
            # Crear orden stop limit con Alpaca
            order_request = StopLimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                stop_price=stop_price,
                limit_price=limit_price,
            )
            
            order = self._alpaca_service.submit_order_request(order_request, user=user)
            
            logger.info(f"Orden stop limit creada: {symbol} {side} {qty} @ stop {stop_price} limit {limit_price}")
            return order
            
        except AlpacaServiceException as e:
            logger.error(f"Error al crear orden stop limit: {str(e)}")
            raise TradingServiceException(f"Error al crear orden stop limit: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear orden stop limit: {str(e)}")
            raise TradingServiceException(f"Error inesperado: {str(e)}")
    
    def create_trailing_stop_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        trail_price: Optional[float] = None,
        trail_percent: Optional[float] = None,
        user: Optional[User] = None,
    ) -> Order:
        """
        Crea una orden trailing stop.
        
        Args:
            symbol: Símbolo del activo
            qty: Cantidad de acciones
            side: Lado de la orden (buy/sell)
            trail_price: Monto del trail en dólares
            trail_percent: Porcentaje del trail
            
        Returns:
            Order: Orden creada
            
        Raises:
            TradingServiceException: Si hay un error al crear la orden
        """
        try:
            if qty <= 0:
                raise TradingServiceException("La cantidad debe ser mayor a cero")
            
            if not trail_price and not trail_percent:
                raise TradingServiceException("Debe especificar trail_price o trail_percent")
            
            # Crear orden trailing stop con Alpaca
            order_request = TrailingStopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                trail_price=trail_price,
                trail_percent=trail_percent,
            )
            
            order = self._alpaca_service.submit_order_request(order_request, user=user)
            
            trail_info = f"${trail_price}" if trail_price else f"{trail_percent}%"
            logger.info(f"Orden trailing stop creada: {symbol} {side} {qty} trail {trail_info}")
            return order
            
        except AlpacaServiceException as e:
            logger.error(f"Error al crear orden trailing stop: {str(e)}")
            raise TradingServiceException(f"Error al crear orden trailing stop: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear orden trailing stop: {str(e)}")
            raise TradingServiceException(f"Error inesperado: {str(e)}")
    
    def create_bracket_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        limit_price: float,
        take_profit: Dict[str, float],
        stop_loss: Dict[str, float],
        user: Optional[User] = None,
    ) -> Order:
        """
        Crea una orden bracket (con take profit y stop loss).
        
        Args:
            symbol: Símbolo del activo
            qty: Cantidad de acciones
            side: Lado de la orden (buy/sell)
            limit_price: Precio límite de entrada
            take_profit: Diccionario con limit_price de take profit
            stop_loss: Diccionario con stop_price y opcional limit_price
            
        Returns:
            Order: Orden principal creada
            
        Raises:
            TradingServiceException: Si hay un error al crear la orden
        """
        try:
            if qty <= 0:
                raise TradingServiceException("La cantidad debe ser mayor a cero")
            
            if limit_price <= 0:
                raise TradingServiceException("El precio límite debe ser mayor a cero")
            
            tp_limit_price = take_profit.get('limit_price', 0)
            sl_stop_price = stop_loss.get('stop_price', 0)
            sl_limit_price = stop_loss.get('limit_price')
            
            if tp_limit_price <= 0:
                raise TradingServiceException("El precio de take profit debe ser mayor a cero")
            
            if sl_stop_price <= 0:
                raise TradingServiceException("El precio de stop loss debe ser mayor a cero")
            
            # Crear objetos de take profit y stop loss
            tp_request = TakeProfitRequest(limit_price=tp_limit_price)
            
            sl_request = StopLossRequest(stop_price=sl_stop_price)
            if sl_limit_price:
                sl_request.limit_price = sl_limit_price
            
            # Crear orden bracket con Alpaca
            order_request = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price,
                order_class=OrderClass.BRACKET,
                take_profit=tp_request,
                stop_loss=sl_request,
            )
            
            order = self._alpaca_service.submit_order_request(order_request, user=user)
            
            logger.info(f"Orden bracket creada: {symbol} {side} {qty} @ {limit_price}, TP: {tp_limit_price}, SL: {sl_stop_price}")
            return order
            
        except AlpacaServiceException as e:
            logger.error(f"Error al crear orden bracket: {str(e)}")
            raise TradingServiceException(f"Error al crear orden bracket: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear orden bracket: {str(e)}")
            raise TradingServiceException(f"Error inesperado: {str(e)}")
    
    # ========================================================================
    # GESTIÓN DE ÓRDENES
    # ========================================================================
    
    def cancel_order(self, order_id: str, user: Optional[User] = None) -> bool:
        """
        Cancela una orden específica.
        
        Args:
            order_id: ID de la orden a cancelar
            
        Returns:
            bool: True si se canceló exitosamente
            
        Raises:
            TradingServiceException: Si hay un error al cancelar
        """
        try:
            return self._alpaca_service.cancel_order(order_id, user=user)
        except AlpacaServiceException as e:
            raise TradingServiceException(f"Error al cancelar orden: {str(e)}")
    
    def get_open_orders(self, user: Optional[User] = None) -> List[Order]:
        """
        Obtiene todas las órdenes abiertas.
        
        Returns:
            List[Order]: Lista de órdenes abiertas
            
        Raises:
            TradingServiceException: Si hay un error al obtener órdenes
        """
        try:
            return self._alpaca_service.get_orders(status='open', user=user)
        except AlpacaServiceException as e:
            raise TradingServiceException(f"Error al obtener órdenes: {str(e)}")
    
    # ========================================================================
    # INFORMACIÓN DE CUENTA Y POSICIONES
    # ========================================================================
    
    def get_account_info(self, user: Optional[User] = None) -> Account:
        """
        Obtiene información de la cuenta.
        
        Returns:
            Account: Información de la cuenta
            
        Raises:
            TradingServiceException: Si hay un error
        """
        try:
            return self._alpaca_service.get_account(user=user)
        except AlpacaServiceException as e:
            raise TradingServiceException(f"Error al obtener cuenta: {str(e)}")
    
    def get_positions(self, user: Optional[User] = None) -> List[Position]:
        """
        Obtiene todas las posiciones abiertas.
        
        Returns:
            List[Position]: Lista de posiciones
            
        Raises:
            TradingServiceException: Si hay un error
        """
        try:
            return self._alpaca_service.get_positions(user=user)
        except AlpacaServiceException as e:
            raise TradingServiceException(f"Error al obtener posiciones: {str(e)}")
    
    def get_portfolio_summary(self, user: Optional[User] = None) -> Dict[str, Any]:
        """
        Obtiene un resumen completo del portafolio.
        
        Returns:
            Dict[str, Any]: Resumen del portafolio
            
        Raises:
            TradingServiceException: Si hay un error
        """
        try:
            account = self._alpaca_service.get_account(user=user)
            positions = self._alpaca_service.get_positions(user=user)
            
            return {
                'account': account.to_dict(),
                'positions': [pos.to_dict() for pos in positions],
                'total_positions': len(positions),
                'total_unrealized_pl': sum(pos.unrealized_pl for pos in positions)
            }
        except AlpacaServiceException as e:
            raise TradingServiceException(f"Error al obtener resumen: {str(e)}")


# Instancia global del servicio
trading_service = TradingService()