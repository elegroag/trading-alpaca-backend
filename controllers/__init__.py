"""
Módulo de controladores.

Exporta los blueprints y funciones de registro de controladores.
"""

from controllers.trading_controller import trading_bp
from controllers.websocket_controller import register_websocket_handlers

__all__ = [
    'trading_bp',
    'register_websocket_handlers'
]
