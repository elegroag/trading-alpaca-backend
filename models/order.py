"""
Modelos de datos para la aplicación de trading.

Define las clases Order, Position, Account y Quote con sus
métodos de conversión desde/hacia Alpaca API.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


class OrderSide(Enum):
    """Lado de la orden (compra/venta)."""
    BUY = 'buy'
    SELL = 'sell'


class OrderType(Enum):
    """Tipo de orden."""
    MARKET = 'market'
    LIMIT = 'limit'
    STOP = 'stop'
    STOP_LIMIT = 'stop_limit'
    TRAILING_STOP = 'trailing_stop'
    BRACKET = 'bracket'


class OrderStatus(Enum):
    """Estado de la orden."""
    NEW = 'new'
    PARTIALLY_FILLED = 'partially_filled'
    FILLED = 'filled'
    DONE_FOR_DAY = 'done_for_day'
    CANCELED = 'canceled'
    EXPIRED = 'expired'
    REPLACED = 'replaced'
    PENDING_CANCEL = 'pending_cancel'
    PENDING_REPLACE = 'pending_replace'
    ACCEPTED = 'accepted'
    PENDING_NEW = 'pending_new'
    ACCEPTED_FOR_BIDDING = 'accepted_for_bidding'
    STOPPED = 'stopped'
    REJECTED = 'rejected'
    SUSPENDED = 'suspended'
    CALCULATED = 'calculated'


@dataclass
class Order:
    """
    Representa una orden de trading.
    
    Attributes:
        symbol: Símbolo del activo
        qty: Cantidad de acciones
        side: Lado de la orden (compra/venta)
        order_type: Tipo de orden
        time_in_force: Duración de la orden
        limit_price: Precio límite (opcional)
        stop_price: Precio stop (opcional)
        order_id: ID de la orden (asignado por Alpaca)
        status: Estado de la orden
        filled_qty: Cantidad ejecutada
        filled_avg_price: Precio promedio de ejecución
        created_at: Fecha de creación
        updated_at: Fecha de actualización
    """
    symbol: str
    qty: float
    side: OrderSide
    order_type: OrderType
    time_in_force: str = 'gtc'
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.NEW
    filled_qty: float = 0.0
    filled_avg_price: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la orden a diccionario."""
        return {
            'order_id': str(self.order_id) if self.order_id else None,
            'symbol': self.symbol,
            'qty': self.qty,
            'side': self.side.value if hasattr(self.side, 'value') else str(self.side),
            'order_type': self.order_type.value if hasattr(self.order_type, 'value') else str(self.order_type),
            'time_in_force': self.time_in_force,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'status': self.status.value if hasattr(self.status, 'value') else str(self.status),
            'filled_qty': self.filled_qty,
            'filled_avg_price': self.filled_avg_price,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_alpaca_order(cls, alpaca_order) -> 'Order':
        """
        Crea una instancia de Order desde un objeto de Alpaca.
        
        Args:
            alpaca_order: Objeto de orden de Alpaca API
            
        Returns:
            Order: Instancia de Order
        """
        # Mapear side
        side = OrderSide.BUY if alpaca_order.side == 'buy' else OrderSide.SELL
        
        # Mapear order_type
        order_type_map = {
            'market': OrderType.MARKET,
            'limit': OrderType.LIMIT,
            'stop': OrderType.STOP,
            'stop_limit': OrderType.STOP_LIMIT
        }
        order_type = order_type_map.get(alpaca_order.type, OrderType.MARKET)
        
        # Mapear status
        status_map = {
            'new': OrderStatus.NEW,
            'partially_filled': OrderStatus.PARTIALLY_FILLED,
            'filled': OrderStatus.FILLED,
            'done_for_day': OrderStatus.DONE_FOR_DAY,
            'canceled': OrderStatus.CANCELED,
            'expired': OrderStatus.EXPIRED,
            'replaced': OrderStatus.REPLACED,
            'pending_cancel': OrderStatus.PENDING_CANCEL,
            'pending_replace': OrderStatus.PENDING_REPLACE,
            'accepted': OrderStatus.ACCEPTED,
            'pending_new': OrderStatus.PENDING_NEW,
            'rejected': OrderStatus.REJECTED,
            'suspended': OrderStatus.SUSPENDED
        }
        status = status_map.get(alpaca_order.status, OrderStatus.NEW)
        
        return cls(
            order_id=str(alpaca_order.id),
            symbol=alpaca_order.symbol,
            qty=float(alpaca_order.qty),
            side=side,
            order_type=order_type,
            time_in_force=alpaca_order.time_in_force,
            limit_price=float(alpaca_order.limit_price) if alpaca_order.limit_price else None,
            stop_price=float(alpaca_order.stop_price) if alpaca_order.stop_price else None,
            status=status,
            filled_qty=float(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0.0,
            filled_avg_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
            created_at=alpaca_order.created_at,
            updated_at=alpaca_order.updated_at
        )


@dataclass
class Position:
    """
    Representa una posición abierta.
    
    Attributes:
        symbol: Símbolo del activo
        qty: Cantidad de acciones
        avg_entry_price: Precio promedio de entrada
        current_price: Precio actual de mercado
        market_value: Valor de mercado actual
        unrealized_pl: P&L no realizado en USD
        unrealized_plpc: P&L no realizado en porcentaje
        side: Lado de la posición (long/short)
    """
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float
    side: str = 'long'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la posición a diccionario."""
        return {
            'symbol': self.symbol,
            'qty': self.qty,
            'avg_entry_price': self.avg_entry_price,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'unrealized_pl': self.unrealized_pl,
            'unrealized_plpc': self.unrealized_plpc,
            'side': self.side
        }
    
    @classmethod
    def from_alpaca_position(cls, alpaca_position) -> 'Position':
        """
        Crea una instancia de Position desde un objeto de Alpaca.
        
        Args:
            alpaca_position: Objeto de posición de Alpaca API
            
        Returns:
            Position: Instancia de Position
        """
        return cls(
            symbol=alpaca_position.symbol,
            qty=float(alpaca_position.qty),
            avg_entry_price=float(alpaca_position.avg_entry_price),
            current_price=float(alpaca_position.current_price),
            market_value=float(alpaca_position.market_value),
            unrealized_pl=float(alpaca_position.unrealized_pl),
            unrealized_plpc=float(alpaca_position.unrealized_plpc) * 100,  # Convertir a porcentaje
            side=alpaca_position.side
        )


@dataclass
class Account:
    """
    Representa la información de la cuenta.
    
    Attributes:
        account_id: ID de la cuenta
        cash: Efectivo disponible
        buying_power: Poder de compra
        portfolio_value: Valor total del portafolio
        equity: Capital total
        currency: Moneda de la cuenta
        status: Estado de la cuenta
    """
    account_id: str
    cash: float
    buying_power: float
    portfolio_value: float
    equity: float
    currency: str = 'USD'
    status: str = 'ACTIVE'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la cuenta a diccionario."""
        return {
            'account_id': self.account_id,
            'cash': self.cash,
            'buying_power': self.buying_power,
            'portfolio_value': self.portfolio_value,
            'equity': self.equity,
            'currency': self.currency,
            'status': self.status
        }
    
    @classmethod
    def from_alpaca_account(cls, alpaca_account) -> 'Account':
        """
        Crea una instancia de Account desde un objeto de Alpaca.
        
        Args:
            alpaca_account: Objeto de cuenta de Alpaca API
            
        Returns:
            Account: Instancia de Account
        """
        return cls(
            account_id=str(alpaca_account.id),
            cash=float(alpaca_account.cash),
            buying_power=float(alpaca_account.buying_power),
            portfolio_value=float(alpaca_account.portfolio_value),
            equity=float(alpaca_account.equity),
            currency=alpaca_account.currency,
            status=alpaca_account.status
        )


@dataclass
class Quote:
    """
    Representa una cotización de mercado.
    
    Attributes:
        symbol: Símbolo del activo
        bid_price: Precio de compra
        ask_price: Precio de venta
        last_price: Último precio negociado
        bid_size: Tamaño del bid
        ask_size: Tamaño del ask
        timestamp: Marca de tiempo
    """
    symbol: str
    bid_price: float
    ask_price: float
    last_price: float
    bid_size: int = 0
    ask_size: int = 0
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la cotización a diccionario."""
        return {
            'symbol': self.symbol,
            'bid_price': self.bid_price,
            'ask_price': self.ask_price,
            'last_price': self.last_price,
            'bid_size': self.bid_size,
            'ask_size': self.ask_size,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
