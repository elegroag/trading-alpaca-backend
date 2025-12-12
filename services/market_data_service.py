"""
Servicio de datos de mercado.

Proporciona funcionalidades adicionales para obtener y procesar
datos de mercado desde Alpaca API.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from services.alpaca_service import alpaca_service, AlpacaServiceException

# Configurar logger
logger = logging.getLogger(__name__)


class MarketDataServiceException(Exception):
    """Excepción personalizada para errores del servicio de datos de mercado."""
    pass


class MarketDataService:
    """
    Servicio para obtener y procesar datos de mercado.
    
    Proporciona métodos de alto nivel para análisis de datos
    y cálculos de indicadores básicos.
    """
    
    def __init__(self):
        """Inicializa el servicio de datos de mercado."""
        self._alpaca_service = alpaca_service
    
    def get_current_price(self, symbol: str) -> float:
        """
        Obtiene el precio actual de un símbolo.
        
        Args:
            symbol: Símbolo del activo
            
        Returns:
            float: Precio actual
        """
        try:
            quote = self._alpaca_service.get_last_quote(symbol)
            return quote['price']
        except AlpacaServiceException as e:
            raise MarketDataServiceException(f"Error al obtener precio: {str(e)}")
    
    def get_price_change(self, symbol: str, timeframe: str = '1D') -> Dict[str, Any]:
        """
        Calcula el cambio de precio para un símbolo.
        
        Args:
            symbol: Símbolo del activo
            timeframe: Marco temporal
            
        Returns:
            Dict con precio actual, anterior, cambio absoluto y porcentual
        """
        try:
            bars = self._alpaca_service.get_bars(symbol, timeframe, limit=2)
            
            if len(bars) < 2:
                raise MarketDataServiceException("Datos insuficientes para calcular cambio")
            
            previous_close = bars[0]['close']
            current_close = bars[1]['close']
            
            change = current_close - previous_close
            change_percent = (change / previous_close) * 100
            
            return {
                'symbol': symbol,
                'current_price': current_close,
                'previous_close': previous_close,
                'change': change,
                'change_percent': change_percent,
                'direction': 'up' if change >= 0 else 'down'
            }
        except AlpacaServiceException as e:
            raise MarketDataServiceException(f"Error al calcular cambio: {str(e)}")
    
    def get_simple_moving_average(
        self, 
        symbol: str, 
        period: int = 20, 
        timeframe: str = '1D'
    ) -> float:
        """
        Calcula la media móvil simple (SMA).
        
        Args:
            symbol: Símbolo del activo
            period: Período de la media móvil
            timeframe: Marco temporal
            
        Returns:
            float: Valor de la SMA
        """
        try:
            bars = self._alpaca_service.get_bars(symbol, timeframe, limit=period)
            
            if len(bars) < period:
                raise MarketDataServiceException(
                    f"Datos insuficientes. Se necesitan {period} barras, hay {len(bars)}"
                )
            
            closes = [bar['close'] for bar in bars]
            sma = sum(closes) / len(closes)
            
            return round(sma, 2)
        except AlpacaServiceException as e:
            raise MarketDataServiceException(f"Error al calcular SMA: {str(e)}")
    
    def get_price_range(self, symbol: str, days: int = 30) -> Dict[str, Any]:
        """
        Obtiene el rango de precios (máximo y mínimo) para un período.
        
        Args:
            symbol: Símbolo del activo
            days: Número de días a analizar
            
        Returns:
            Dict con precio máximo, mínimo y rango
        """
        try:
            bars = self._alpaca_service.get_bars(symbol, '1D', limit=days)
            
            if not bars:
                raise MarketDataServiceException("No hay datos disponibles")
            
            highs = [bar['high'] for bar in bars]
            lows = [bar['low'] for bar in bars]
            
            high = max(highs)
            low = min(lows)
            
            return {
                'symbol': symbol,
                'period_days': days,
                'high': high,
                'low': low,
                'range': high - low,
                'range_percent': ((high - low) / low) * 100
            }
        except AlpacaServiceException as e:
            raise MarketDataServiceException(f"Error al obtener rango: {str(e)}")


# Instancia global del servicio
market_data_service = MarketDataService()
