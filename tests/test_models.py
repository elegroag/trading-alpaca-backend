"""
Tests para los modelos de datos.
"""

import pytest
from models.order import Order, OrderSide, OrderType, OrderStatus, Position, Account, Quote


class TestOrder:
    """Tests para la clase Order."""
    
    def test_create_market_order(self):
        """Verifica la creación de una orden de mercado."""
        order = Order(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        assert order.symbol == 'AAPL'
        assert order.qty == 10
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.time_in_force == 'gtc'
    
    def test_create_limit_order(self):
        """Verifica la creación de una orden límite."""
        order = Order(
            symbol='GOOGL',
            qty=5,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            limit_price=150.00
        )
        
        assert order.symbol == 'GOOGL'
        assert order.limit_price == 150.00
        assert order.order_type == OrderType.LIMIT
    
    def test_order_to_dict(self):
        """Verifica la conversión de orden a diccionario."""
        order = Order(
            symbol='TSLA',
            qty=1,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            order_id='test-123'
        )
        
        order_dict = order.to_dict()
        
        assert order_dict['symbol'] == 'TSLA'
        assert order_dict['qty'] == 1
        assert order_dict['side'] == 'buy'
        assert order_dict['order_type'] == 'market'
        assert order_dict['order_id'] == 'test-123'


class TestPosition:
    """Tests para la clase Position."""
    
    def test_create_position(self):
        """Verifica la creación de una posición."""
        position = Position(
            symbol='AAPL',
            qty=100,
            avg_entry_price=150.00,
            current_price=155.00,
            market_value=15500.00,
            unrealized_pl=500.00,
            unrealized_plpc=3.33
        )
        
        assert position.symbol == 'AAPL'
        assert position.qty == 100
        assert position.unrealized_pl == 500.00
    
    def test_position_to_dict(self):
        """Verifica la conversión de posición a diccionario."""
        position = Position(
            symbol='MSFT',
            qty=50,
            avg_entry_price=300.00,
            current_price=310.00,
            market_value=15500.00,
            unrealized_pl=500.00,
            unrealized_plpc=3.33
        )
        
        pos_dict = position.to_dict()
        
        assert pos_dict['symbol'] == 'MSFT'
        assert pos_dict['qty'] == 50


class TestAccount:
    """Tests para la clase Account."""
    
    def test_create_account(self):
        """Verifica la creación de una cuenta."""
        account = Account(
            account_id='test-account',
            cash=10000.00,
            buying_power=20000.00,
            portfolio_value=50000.00,
            equity=50000.00
        )
        
        assert account.cash == 10000.00
        assert account.buying_power == 20000.00
        assert account.currency == 'USD'
    
    def test_account_to_dict(self):
        """Verifica la conversión de cuenta a diccionario."""
        account = Account(
            account_id='test-account',
            cash=10000.00,
            buying_power=20000.00,
            portfolio_value=50000.00,
            equity=50000.00
        )
        
        acc_dict = account.to_dict()
        
        assert acc_dict['cash'] == 10000.00
        assert acc_dict['status'] == 'ACTIVE'


class TestQuote:
    """Tests para la clase Quote."""
    
    def test_create_quote(self):
        """Verifica la creación de una cotización."""
        quote = Quote(
            symbol='AAPL',
            bid_price=149.50,
            ask_price=150.50,
            last_price=150.00
        )
        
        assert quote.symbol == 'AAPL'
        assert quote.bid_price == 149.50
        assert quote.ask_price == 150.50
        assert quote.last_price == 150.00
