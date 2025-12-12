"""
Servicio de cálculo de Fair Value para trading swing.

Implementa múltiples métodos de cálculo:
- Z-Score: Detecta sobrecompra/sobreventa estadística
- ATR: Precios adaptados a volatilidad del mercado
- EMA (Mean Reversion): Puntos de reversión a la media
- Soportes/Resistencias: Puntos clave de reversión reales
"""

from typing import Optional, Dict, Any
import pandas as pd
import numpy as np


class FairValueServiceException(Exception):
    pass


class FairValueService:
    """Calcula valores justos de entrada/salida para swing trading."""

    def calculate_fair_value(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calcula fair values usando múltiples métodos.
        
        Args:
            df: DataFrame con columnas 'open', 'high', 'low', 'close', 'volume'
        
        Returns:
            Dict con fair values, señales y recomendaciones
        """
        if df.empty or len(df) < 20:
            raise FairValueServiceException(
                "Se requieren al menos 20 barras para calcular fair value"
            )

        df = df.copy()

        # EMA 20 y 50
        df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

        # ATR (Average True Range) - 14 períodos
        df["H-L"] = df["high"] - df["low"]
        df["H-PC"] = (df["high"] - df["close"].shift()).abs()
        df["L-PC"] = (df["low"] - df["close"].shift()).abs()
        df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
        df["ATR"] = df["TR"].rolling(14).mean()

        # Z-Score (20 días)
        df["mean20"] = df["close"].rolling(20).mean()
        df["std20"] = df["close"].rolling(20).std()
        df["zscore"] = (df["close"] - df["mean20"]) / df["std20"]

        # Soportes y Resistencias (20 días)
        df["Support20"] = df["low"].rolling(20).min()
        df["Resistance20"] = df["high"].rolling(20).max()

        # Eliminar filas con NaN
        df = df.dropna()

        if df.empty:
            raise FairValueServiceException(
                "No hay suficientes datos después de calcular indicadores"
            )

        last = df.iloc[-1]
        current_price = float(last["close"])

        # ===== CÁLCULOS DE FAIR VALUE =====

        # 1. Método ATR
        fair_buy_atr = float(last["EMA20"] - 0.5 * last["ATR"])
        fair_sell_atr = float(last["EMA20"] + 0.5 * last["ATR"])

        # 2. Método EMA (Mean Reversion)
        fair_buy_ema = float(last["EMA20"] * 0.995)
        fair_sell_ema = float(last["EMA20"] * 1.005)

        # 3. Método Soportes/Resistencias
        fair_buy_support = float(last["Support20"] * 1.01)
        fair_sell_resistance = float(last["Resistance20"] * 0.99)

        # 4. Z-Score actual
        zscore = float(last["zscore"])

        # ===== SEÑALES DE TRADING =====
        signals = self._generate_signals(
            current_price=current_price,
            zscore=zscore,
            fair_buy_atr=fair_buy_atr,
            fair_sell_atr=fair_sell_atr,
            fair_buy_ema=fair_buy_ema,
            fair_sell_ema=fair_sell_ema,
            fair_buy_support=fair_buy_support,
            fair_sell_resistance=fair_sell_resistance,
            ema20=float(last["EMA20"]),
            ema50=float(last["EMA50"]),
        )

        # ===== RANGOS CONSOLIDADOS =====
        buy_range = {
            "min": round(min(fair_buy_atr, fair_buy_ema, fair_buy_support), 2),
            "max": round(max(fair_buy_atr, fair_buy_ema, fair_buy_support), 2),
        }
        sell_range = {
            "min": round(min(fair_sell_atr, fair_sell_ema, fair_sell_resistance), 2),
            "max": round(max(fair_sell_atr, fair_sell_ema, fair_sell_resistance), 2),
        }

        return {
            "current_price": round(current_price, 2),
            "zscore": round(zscore, 2),
            "ema20": round(float(last["EMA20"]), 2),
            "ema50": round(float(last["EMA50"]), 2),
            "atr": round(float(last["ATR"]), 2),
            "support20": round(float(last["Support20"]), 2),
            "resistance20": round(float(last["Resistance20"]), 2),
            "fair_values": {
                "atr": {
                    "buy": round(fair_buy_atr, 2),
                    "sell": round(fair_sell_atr, 2),
                },
                "ema": {
                    "buy": round(fair_buy_ema, 2),
                    "sell": round(fair_sell_ema, 2),
                },
                "support_resistance": {
                    "buy": round(fair_buy_support, 2),
                    "sell": round(fair_sell_resistance, 2),
                },
            },
            "buy_range": buy_range,
            "sell_range": sell_range,
            "signals": signals,
        }

    def _generate_signals(
        self,
        current_price: float,
        zscore: float,
        fair_buy_atr: float,
        fair_sell_atr: float,
        fair_buy_ema: float,
        fair_sell_ema: float,
        fair_buy_support: float,
        fair_sell_resistance: float,
        ema20: float,
        ema50: float,
    ) -> Dict[str, Any]:
        """Genera señales de trading basadas en los fair values calculados."""

        signals_list = []
        buy_signals = 0
        sell_signals = 0
        neutral_signals = 0

        # 1. Señal Z-Score
        if zscore <= -1.0:
            signals_list.append({
                "method": "Z-Score",
                "signal": "COMPRA",
                "strength": "fuerte" if zscore <= -1.5 else "moderada",
                "reason": f"Precio estadísticamente barato (Z={zscore:.2f})",
            })
            buy_signals += 2 if zscore <= -1.5 else 1
        elif zscore >= 1.0:
            signals_list.append({
                "method": "Z-Score",
                "signal": "VENTA",
                "strength": "fuerte" if zscore >= 1.5 else "moderada",
                "reason": f"Precio estadísticamente caro (Z={zscore:.2f})",
            })
            sell_signals += 2 if zscore >= 1.5 else 1
        else:
            signals_list.append({
                "method": "Z-Score",
                "signal": "NEUTRAL",
                "strength": "neutral",
                "reason": f"Precio en rango normal (Z={zscore:.2f})",
            })
            neutral_signals += 1

        # 2. Señal ATR
        if current_price <= fair_buy_atr:
            signals_list.append({
                "method": "ATR",
                "signal": "COMPRA",
                "strength": "moderada",
                "reason": f"Precio por debajo de zona de compra ATR (${fair_buy_atr:.2f})",
            })
            buy_signals += 1
        elif current_price >= fair_sell_atr:
            signals_list.append({
                "method": "ATR",
                "signal": "VENTA",
                "strength": "moderada",
                "reason": f"Precio por encima de zona de venta ATR (${fair_sell_atr:.2f})",
            })
            sell_signals += 1
        else:
            signals_list.append({
                "method": "ATR",
                "signal": "NEUTRAL",
                "strength": "neutral",
                "reason": "Precio dentro de rango ATR",
            })
            neutral_signals += 1

        # 3. Señal EMA (Mean Reversion)
        if current_price <= fair_buy_ema:
            signals_list.append({
                "method": "EMA",
                "signal": "COMPRA",
                "strength": "moderada",
                "reason": f"Precio por debajo de EMA20 -0.5% (${fair_buy_ema:.2f})",
            })
            buy_signals += 1
        elif current_price >= fair_sell_ema:
            signals_list.append({
                "method": "EMA",
                "signal": "VENTA",
                "strength": "moderada",
                "reason": f"Precio por encima de EMA20 +0.5% (${fair_sell_ema:.2f})",
            })
            sell_signals += 1
        else:
            signals_list.append({
                "method": "EMA",
                "signal": "NEUTRAL",
                "strength": "neutral",
                "reason": "Precio cerca de EMA20",
            })
            neutral_signals += 1

        # 4. Señal Soporte/Resistencia
        if current_price <= fair_buy_support:
            signals_list.append({
                "method": "Soporte/Resistencia",
                "signal": "COMPRA",
                "strength": "fuerte",
                "reason": f"Precio cerca del soporte de 20 días (${fair_buy_support:.2f})",
            })
            buy_signals += 2
        elif current_price >= fair_sell_resistance:
            signals_list.append({
                "method": "Soporte/Resistencia",
                "signal": "VENTA",
                "strength": "fuerte",
                "reason": f"Precio cerca de la resistencia de 20 días (${fair_sell_resistance:.2f})",
            })
            sell_signals += 2
        else:
            signals_list.append({
                "method": "Soporte/Resistencia",
                "signal": "NEUTRAL",
                "strength": "neutral",
                "reason": "Precio entre soporte y resistencia",
            })
            neutral_signals += 1

        # 5. Señal cruce EMA
        if ema20 > ema50:
            signals_list.append({
                "method": "Cruce EMA",
                "signal": "ALCISTA",
                "strength": "moderada",
                "reason": "EMA20 por encima de EMA50 (tendencia alcista)",
            })
            buy_signals += 1
        elif ema20 < ema50:
            signals_list.append({
                "method": "Cruce EMA",
                "signal": "BAJISTA",
                "strength": "moderada",
                "reason": "EMA20 por debajo de EMA50 (tendencia bajista)",
            })
            sell_signals += 1
        else:
            signals_list.append({
                "method": "Cruce EMA",
                "signal": "NEUTRAL",
                "strength": "neutral",
                "reason": "EMAs convergentes",
            })
            neutral_signals += 1

        # Recomendación consolidada
        total_score = buy_signals - sell_signals

        if total_score >= 3:
            recommendation = "COMPRA FUERTE"
            recommendation_color = "success"
        elif total_score >= 1:
            recommendation = "COMPRA"
            recommendation_color = "success"
        elif total_score <= -3:
            recommendation = "VENTA FUERTE"
            recommendation_color = "error"
        elif total_score <= -1:
            recommendation = "VENTA"
            recommendation_color = "error"
        else:
            recommendation = "MANTENER"
            recommendation_color = "warning"

        return {
            "signals": signals_list,
            "buy_score": buy_signals,
            "sell_score": sell_signals,
            "neutral_score": neutral_signals,
            "total_score": total_score,
            "recommendation": recommendation,
            "recommendation_color": recommendation_color,
        }


fair_value_service = FairValueService()
