"""
Módulo de configuración de la aplicación.

Implementa el patrón Singleton para garantizar una única instancia
de configuración durante el ciclo de vida de la aplicación.
"""

import os
from typing import Tuple, List
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class Config:
    """
    Clase de configuración con patrón Singleton.
    
    Centraliza todas las configuraciones de la aplicación,
    incluyendo credenciales de Alpaca, configuración de Flask
    y parámetros de trading.
    """
    
    _instance = None
    
    def __new__(cls):
        """Implementación del patrón Singleton."""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Inicializa la configuración desde variables de entorno."""
        if self._initialized:
            return
        
        # Credenciales de Alpaca
        self.ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
        self.ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY', '')
        self.ALPACA_BASE_URL = os.getenv(
            'ALPACA_BASE_URL', 
            'https://paper-api.alpaca.markets'
        )
        
        # Configuración de Flask
        self.SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
        self.DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
        
        # Configuración de SocketIO
        self.SOCKETIO_ASYNC_MODE = os.getenv('SOCKETIO_ASYNC_MODE', 'threading')
        self.SOCKETIO_PING_TIMEOUT = int(os.getenv('SOCKETIO_PING_TIMEOUT', '60'))
        self.SOCKETIO_PING_INTERVAL = int(os.getenv('SOCKETIO_PING_INTERVAL', '25'))
        
        # Límites de trading
        self.MIN_ORDER_SIZE = float(os.getenv('MIN_ORDER_SIZE', '1.0'))
        self.MAX_ORDER_SIZE = float(os.getenv('MAX_ORDER_SIZE', '100000.0'))
        
        # Configuración de datos de mercado
        self.DEFAULT_TIMEFRAME = os.getenv('DEFAULT_TIMEFRAME', '1D')
        self.DEFAULT_BARS_LIMIT = int(os.getenv('DEFAULT_BARS_LIMIT', '100'))
        self.MAX_BARS_MIN = int(os.getenv('MAX_BARS_MIN', '390'))
        self.MAX_BARS_HOUR = int(os.getenv('MAX_BARS_HOUR', '400'))
        self.MAX_BARS_DAY = int(os.getenv('MAX_BARS_DAY', '252'))

        # Auto-trading swing (desactivado por defecto)
        self.SWING_AUTOTRADE_ENABLED = os.getenv('SWING_AUTOTRADE_ENABLED', 'false').lower() == 'true'

        # Configuración de base de datos
        self.MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
        self.MONGO_DB = os.getenv('MONGO_DB', 'trading_swing')

        # Configuración de seguridad
        self.FERNET_KEY = os.getenv('FERNET_KEY', '')
        self.JWT_EXPIRES_MIN = int(os.getenv('JWT_EXPIRES_MIN', '60'))
        self.JWT_ALGORITHM = 'HS256'

        self._initialized = True
    
    def validate(self) -> Tuple[bool, List[str]]:
        """
        Valida que la configuración esté completa.
        
        Returns:
            Tuple[bool, List[str]]: (es_válida, lista_de_errores)
        """
        errors = []
        
        if not self.ALPACA_API_KEY:
            errors.append("ALPACA_API_KEY no está configurada")
        
        if not self.ALPACA_SECRET_KEY:
            errors.append("ALPACA_SECRET_KEY no está configurada")
        
        if not self.SECRET_KEY or self.SECRET_KEY == 'dev-secret-key-change-in-production':
            if not self.DEBUG:
                errors.append("SECRET_KEY debe configurarse en producción")

        if not self.MONGO_URI:
            errors.append("MONGO_URI no está configurada")

        if not self.MONGO_DB:
            errors.append("MONGO_DB no está configurada")

        if not self.FERNET_KEY:
            errors.append("FERNET_KEY no está configurada")
        
        return len(errors) == 0, errors
    
    def to_dict(self) -> dict:
        """
        Convierte la configuración a diccionario (sin datos sensibles).
        
        Returns:
            dict: Configuración sin datos sensibles
        """
        return {
            'ALPACA_BASE_URL': self.ALPACA_BASE_URL,
            'DEBUG': self.DEBUG,
            'SOCKETIO_ASYNC_MODE': self.SOCKETIO_ASYNC_MODE,
            'MIN_ORDER_SIZE': self.MIN_ORDER_SIZE,
            'MAX_ORDER_SIZE': self.MAX_ORDER_SIZE,
            'DEFAULT_TIMEFRAME': self.DEFAULT_TIMEFRAME,
            'DEFAULT_BARS_LIMIT': self.DEFAULT_BARS_LIMIT,
            'MAX_BARS_MIN': self.MAX_BARS_MIN,
            'MAX_BARS_HOUR': self.MAX_BARS_HOUR,
            'MAX_BARS_DAY': self.MAX_BARS_DAY,
            'ALPACA_API_KEY_SET': bool(self.ALPACA_API_KEY),
            'ALPACA_SECRET_KEY_SET': bool(self.ALPACA_SECRET_KEY),
            'MONGO_URI_SET': bool(self.MONGO_URI),
            'MONGO_DB': self.MONGO_DB,
            'FERNET_KEY_SET': bool(self.FERNET_KEY),
            'JWT_EXPIRES_MIN': self.JWT_EXPIRES_MIN,
            'SWING_AUTOTRADE_ENABLED': self.SWING_AUTOTRADE_ENABLED,
        }


# Instancia global de configuración
config = Config()
