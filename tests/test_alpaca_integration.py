"""Tests de integración para AlpacaService usando alpaca-py.

Requiere ALPACA_API_KEY y ALPACA_SECRET_KEY configuradas.
Todas las pruebas del módulo se saltan automáticamente si no hay credenciales.
"""

import os

import pytest

from services.alpaca_service import alpaca_service
from models.order import Order, OrderSide, OrderType


HAS_ALPACA_KEYS = bool(
    os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY")
)

# Saltar todo el módulo si no hay credenciales configuradas
pytestmark = pytest.mark.skipif(
    not HAS_ALPACA_KEYS,
    reason="Variables de entorno ALPACA_API_KEY y ALPACA_SECRET_KEY no configuradas",
)


def test_get_account_returns_account():
    """Verifica que la cuenta se obtenga correctamente desde Alpaca."""
    account = alpaca_service.get_account()

    assert account.account_id
    assert account.cash is not None
    assert account.buying_power is not None


def test_get_last_quote_returns_price():
    """Verifica que se obtenga una cotización válida para un símbolo."""
    symbol = os.getenv("ALPACA_TEST_SYMBOL", "AAPL")

    quote = alpaca_service.get_last_quote(symbol)

    assert quote["symbol"] == symbol
    assert quote["price"] > 0
    assert "timestamp" in quote and quote["timestamp"] is not None


def test_get_bars_returns_bars():
    """Verifica que se obtengan barras históricas para un símbolo."""
    symbol = os.getenv("ALPACA_TEST_SYMBOL", "AAPL")

    bars = alpaca_service.get_bars(symbol, timeframe="1D", limit=5)

    assert isinstance(bars, list)
    assert len(bars) > 0

    bar = bars[0]
    for key in ("timestamp", "open", "high", "low", "close", "volume"):
        assert key in bar


@pytest.mark.skipif(
    not os.getenv("ALPACA_ENABLE_ORDER_TEST"),
    reason="Setear ALPACA_ENABLE_ORDER_TEST=1 para probar envío de orden real en paper",
)
def test_submit_market_order_paper():
    """Envía una orden de mercado pequeña en entorno paper controlada por variable de entorno."""
    symbol = os.getenv("ALPACA_TEST_ORDER_SYMBOL", "AAPL")

    order = Order(
        symbol=symbol,
        qty=1,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        time_in_force="day",
    )

    created = alpaca_service.submit_order(order)

    assert created.order_id is not None
    assert created.symbol == symbol
    assert created.qty > 0
