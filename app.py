"""
Aplicación principal Flask con WebSocket para Trading Swing.

Implementa el patrón MVC y proporciona endpoints REST y WebSocket
para operaciones de trading en tiempo real.
"""

import os

from dotenv import load_dotenv

load_dotenv()

if os.getenv('SOCKETIO_ASYNC_MODE', 'threading').lower() == 'eventlet':
    import eventlet

    eventlet.monkey_patch()

import logging

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO

from config import config
from routes.auth_routes import register_auth_routes
from routes.user_routes import register_user_routes
from routes.screener_routes import register_screener_routes
from routes.trading_routes import register_trading_routes
from sockets.ws_events import register_socket_handlers


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Inicializar SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode=config.SOCKETIO_ASYNC_MODE,
    ping_timeout=config.SOCKETIO_PING_TIMEOUT,
    ping_interval=config.SOCKETIO_PING_INTERVAL
)

# Registrar rutas
register_auth_routes(app)
register_user_routes(app)
register_screener_routes(app)
register_trading_routes(app, socketio)
register_socket_handlers(socketio)


@app.route('/')
def index():
    try:
        is_valid, errors = config.validate()
        if not is_valid:
            logger.error(f"Configuración inválida: {errors}")
            return jsonify({
                'success': False,
                'error': 'Configuración inválida',
                'details': errors,
            }), 500

        return jsonify({
            'success': True,
            'data': {
                'status': 'ok',
            },
        })
    except Exception as e:
        logger.error(f"Error al procesar healthcheck: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor',
        }), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Maneja errores 404."""
    return jsonify({
        'success': False,
        'error': 'Recurso no encontrado'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Maneja errores 500."""
    logger.error(f"Error interno: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'Error interno del servidor'
    }), 500


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == '__main__':
    logger.info("Iniciando aplicación de Trading Swing...")
    logger.info(f"Modo: {'Desarrollo' if config.DEBUG else 'Producción'}")
    logger.info(f"Alpaca URL: {config.ALPACA_BASE_URL}")
    
    # Validar configuración
    is_valid, errors = config.validate()
    if not is_valid:
        logger.error("Error en la configuración:")
        for error in errors:
            logger.error(f"  - {error}")
        exit(1)
    
    # Iniciar servidor
    socketio.run(
        app,
        debug=config.DEBUG,
        host='0.0.0.0',
        port=5080
    )