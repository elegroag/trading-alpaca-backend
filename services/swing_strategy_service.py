"""
Servicio de estrategia Swing usando Alpaca (alpaca-py).

Reutiliza alpaca_service para obtener datos y cuenta, y ejecuta
órdenes bracket (entrada + take profit + stop loss) según una
estrategia simple de tendencia + RSI + ATR.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import (
    MarketOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
)

from services.alpaca_service import alpaca_service, AlpacaServiceException
from models.user import User


# ------------------ PARÁMETROS DE ESTRATEGIA ------------------ #

RISK_PER_TRADE = 0.01     # 1% del equity por operación
MAX_POSITIONS = 5         # (no usado aún aquí, pero previsto)
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5
RR = 2.0                  # Risk/Reward 2:1 por defecto


@dataclass
class SwingSignal:
    """Representa la señal y parámetros calculados para un símbolo."""
    symbol: str
    has_signal: bool
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    qty: Optional[int] = None
    reason: Optional[str] = None


class SwingStrategyServiceException(Exception):
    """Errores propios del servicio de estrategia swing."""
    pass


class SwingStrategyService:
    """
    Servicio que implementa la lógica de la estrategia swing.

    - Usa alpaca_service para cuenta y barras históricas.
    - Calcula EMA(20), EMA(50), RSI(14), ATR(14).
    - Condiciones de compra:
        * EMA rápida > EMA lenta (tendencia alcista)
        * Cierre actual > EMA rápida
        * RSI entre 40 y 65
    - Calcula tamaño de posición por riesgo (% equity) y coloca
      orden bracket (market + TP + SL).
    """

    def __init__(self):
        # Reutilizamos el cliente de trading interno de alpaca_service
        # para no crear conexiones duplicadas.
        self._trading_client = alpaca_service._trading_client

    # ---------- INDICADORES ---------- #

    @staticmethod
    def _ema(series: pd.Series, period: int) -> pd.Series:
        """EMA clásica usando pandas."""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """RSI clásico de cierre."""
        delta = series.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ma_up = up.rolling(window=period, min_periods=period).mean()
        ma_down = down.rolling(window=period, min_periods=period).mean()
        rs = ma_up / ma_down
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """ATR clásico sobre high/low/close."""
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    # ---------- LÓGICA DE SEÑAL ---------- #

    def _build_df(self, symbol: str, limit: int = 300, user: Optional[User] = None) -> pd.DataFrame:
        """
        Construye un DataFrame OHLCV diario a partir de alpaca_service.

        Usamos get_bars('1D') para los últimos `limit` períodos.
        """
        bars = alpaca_service.get_bars(symbol, timeframe="1D", limit=limit, user=user)
        if not bars:
            raise SwingStrategyServiceException(f"Sin barras para {symbol}")

        df = pd.DataFrame(bars)
        # Nos aseguramos de que las columnas necesarias estén como float
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        return df

    def generate_signal(self, symbol: str, user: Optional[User] = None) -> SwingSignal:
        """
        Genera la señal swing para un símbolo SIN enviar orden.

        Devuelve SwingSignal con parámetros calculados si hay señal,
        o has_signal=False con 'reason' si no hay setup.
        """
        try:
            df = self._build_df(symbol, limit=300, user=user)
        except AlpacaServiceException as e:
            return SwingSignal(symbol=symbol, has_signal=False, reason=str(e))
        except Exception as e:
            return SwingSignal(symbol=symbol, has_signal=False, reason=str(e))

        # Calcular indicadores
        df["ema_fast"] = self._ema(df["close"], EMA_FAST)
        df["ema_slow"] = self._ema(df["close"], EMA_SLOW)
        df["rsi"] = self._rsi(df["close"], RSI_PERIOD)
        df["atr"] = self._atr(df, ATR_PERIOD)

        latest = df.iloc[-1]

        # Reglas de tendencia y señal
        trend_up = latest["ema_fast"] > latest["ema_slow"]
        price_above_ema = latest["close"] > latest["ema_fast"]
        rsi_ok = 40 <= latest["rsi"] <= 65

        signal_buy = bool(trend_up and price_above_ema and rsi_ok)

        if not signal_buy:
            return SwingSignal(
                symbol=symbol,
                has_signal=False,
                reason="No cumple condiciones de tendencia/RSI",
            )

        # Gestión de riesgo y tamaños
        try:
            account = alpaca_service.get_account(user=user)
        except AlpacaServiceException as e:
            return SwingSignal(symbol=symbol, has_signal=False, reason=str(e))

        equity = float(account.equity)
        risk_amount = equity * RISK_PER_TRADE

        entry_price = float(latest["close"])
        atr_val = float(latest["atr"])

        if np.isnan(atr_val) or atr_val <= 0:
            return SwingSignal(symbol=symbol, has_signal=False, reason="ATR inválida")

        stop_distance = ATR_MULTIPLIER * atr_val
        stop_price = round(entry_price - stop_distance, 2)

        if stop_price <= 0:
            return SwingSignal(symbol=symbol, has_signal=False, reason="stop_price inválido")

        # Cantidad por riesgo
        riesgo_por_accion = entry_price - stop_price
        if riesgo_por_accion <= 0:
            return SwingSignal(symbol=symbol, has_signal=False, reason="riesgo_por_accion <= 0")

        qty = math.floor(risk_amount / riesgo_por_accion)
        if qty <= 0:
            return SwingSignal(
                symbol=symbol,
                has_signal=False,
                reason="qty calculada 0 (riesgo/stop muy pequeño)",
            )

        # Take profit por RR 2:1 (configurable)
        tp_price = round(entry_price + RR * riesgo_por_accion, 2)

        return SwingSignal(
            symbol=symbol,
            has_signal=True,
            entry_price=entry_price,
            stop_price=stop_price,
            take_profit_price=tp_price,
            qty=qty,
        )

    # ---------- EJECUCIÓN DE ÓRDENES ---------- #

    def execute_signal(self, signal: SwingSignal, user: Optional[User] = None):
        """
        Ejecuta una orden bracket en Alpaca para una señal válida.

        Lanza excepción si has_signal=False o si falla el envío.
        """
        if not signal.has_signal:
            raise SwingStrategyServiceException("No se puede ejecutar: la señal no es válida")

        order_request = MarketOrderRequest(
            symbol=signal.symbol,
            qty=signal.qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class="bracket",
            take_profit=TakeProfitRequest(limit_price=str(signal.take_profit_price)),
            stop_loss=StopLossRequest(stop_price=str(signal.stop_price)),
        )

        try:
            client = alpaca_service._get_trading_client_for_user(user)  # type: ignore[attr-defined]
            order = client.submit_order(order_request)
            return order
        except Exception as e:
            raise SwingStrategyServiceException(f"Error enviando orden bracket: {e}")

    def scan_and_trade(self, tickers: List[str], user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Recorre una lista de símbolos, genera señal y, si es válida,
        envía la orden bracket correspondiente.

        Devuelve un resumen por ticker.
        """
        results: List[Dict[str, Any]] = []

        for symbol in tickers:
            signal = self.generate_signal(symbol, user=user)
            summary: Dict[str, Any] = {
                "symbol": symbol,
                "has_signal": signal.has_signal,
                "reason": signal.reason,
            }

            if not signal.has_signal:
                results.append(summary)
                continue

            try:
                order = self.execute_signal(signal, user=user)
                order_id = getattr(order, "id", None)
                if order_id is not None:
                    order_id = str(order_id)

                status = getattr(order, "status", None)
                if status is not None:
                    status = str(status)

                summary.update(
                    {
                        "qty": signal.qty,
                        "entry_price": signal.entry_price,
                        "stop_price": signal.stop_price,
                        "take_profit_price": signal.take_profit_price,
                        "order_id": order_id,
                        "status": status,
                    }
                )
            except SwingStrategyServiceException as e:
                summary["error"] = str(e)

            results.append(summary)

        return results


# Instancia global del servicio
swing_strategy_service = SwingStrategyService()