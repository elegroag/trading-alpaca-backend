# swing_alpaca.py
import os
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

# Alpaca SDK (alpaca-py)
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# ---------- CONFIG ----------
API_KEY = os.getenv("APCA_API_KEY_ID")
API_SECRET = os.getenv("APCA_API_SECRET_KEY")
PAPER = True  # usar paper en pruebas

RISK_PER_TRADE = 0.01   # 1% por operación
MAX_POSITIONS = 5
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5
RR = 2.0  # objetivo 2:1

# Lista de tickers (ejemplo). En práctica, usa filtrado por volumen/líquidez.
TICKERS = ["AAPL", "MSFT", "AMZN", "NVDA", "META"]

# ---------- UTILIDADES INDICADORES ----------
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.rolling(window=period, min_periods=period).mean()
    ma_down = down.rolling(window=period, min_periods=period).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

# ---------- INICIALIZAR CLIENTES ----------
trading_client = TradingClient(API_KEY, API_SECRET, paper=PAPER)
historical_client = StockHistoricalDataClient(API_KEY, API_SECRET)

# ---------- FUNCION PRINCIPAL (un ciclo diario) ----------
def check_and_trade(symbol):
    # obtener barras diarias (ultimos 300 dias)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=400)
    req = StockBarsRequest(symbol_or_symbols=[symbol], timeframe=TimeFrame.Day, start=start, end=end)
    bars = historical_client.get_stock_bars(req)
    df = bars.df[symbol].copy()  # dataframe con columns: open, high, low, close, volume

    # calcular indicadores
    df['ema_fast'] = ema(df['close'], EMA_FAST)
    df['ema_slow'] = ema(df['close'], EMA_SLOW)
    df['rsi'] = rsi(df['close'], RSI_PERIOD)
    df['atr'] = atr(df, ATR_PERIOD)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # reglas de tendencia y señal
    trend_up = latest['ema_fast'] > latest['ema_slow']
    price_above_ema = latest['close'] > latest['ema_fast']
    rsi_ok = 40 <= latest['rsi'] <= 65

    signal_buy = trend_up and price_above_ema and rsi_ok

    if not signal_buy:
        print(f"{symbol}: no signal")
        return None

    # calcular tamaño por riesgo
    account = trading_client.get_account()
    equity = float(account.equity)  # saldo total
    risk_amount = equity * RISK_PER_TRADE

    entry_price = latest['close']
    atr_val = latest['atr']
    if np.isnan(atr_val) or atr_val <= 0:
        print(f"{symbol}: ATR inválida")
        return None

    stop_distance = ATR_MULTIPLIER * atr_val
    stop_price = round(entry_price - stop_distance, 2)
    if stop_price <= 0:
        print(f"{symbol}: stop_price inválido")
        return None

    qty = math.floor(risk_amount / (entry_price - stop_price))
    if qty <= 0:
        print(f"{symbol}: qty calculada 0 (riesgo/stop muy pequeño)")
        return None

    # calcular take-profit
    tp_price = round(entry_price + RR * (entry_price - stop_price), 2)

    # crear bracket order (market entry + stop + take profit)
    order_request = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        order_class="bracket",  # bracket order
        take_profit=TakeProfitRequest(limit_price=str(tp_price)),
        stop_loss=StopLossRequest(stop_price=str(stop_price))
    )

    # enviar orden
    try:
        order = trading_client.submit_order(order_request)
        print(f"Orden enviada para {symbol}: qty={qty}, entry≈{entry_price}, stop={stop_price}, tp={tp_price}")
        return order
    except Exception as e:
        print("Error enviando orden:", e)
        return None

# ---------- EJECUTAR BARRIDO SOBRE TICKERS ----------
if __name__ == "__main__":
    for t in TICKERS:
        check_and_trade(t)
