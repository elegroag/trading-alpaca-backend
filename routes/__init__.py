"""
Módulo de modelos de datos.

Exporta todas las clases de modelos para facilitar las importaciones.
"""

from .user_routes import register_user_routes
from .preferences_router import register_preferences_routes
from .trading_routes import register_trading_routes
from .auth_routes import register_auth_routes
from .favorites_router import register_favorites_routes
from .news_routes import register_news_routes
from .screener_routes import register_screener_routes

__all__ = [
    'register_user_routes',
    'register_preferences_routes',
    'register_trading_routes',
    'register_auth_routes',
    'register_favorites_routes',
    'register_news_routes',
    'register_screener_routes',
]
