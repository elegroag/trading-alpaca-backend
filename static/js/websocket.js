/**
 * Cliente WebSocket para comunicación en tiempo real.
 *
 * Implementa el patrón Observer para manejar eventos del servidor
 * y actualizar la UI en tiempo real.
 */

class WebSocketClient {
  /**
   * Constructor del cliente WebSocket.
   */
  constructor() {
    this.socket = null;
    this.connected = false;
    this.subscribers = {};
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  /**
   * Conecta al servidor WebSocket.
   */
  connect() {
    console.log('Conectando a WebSocket...');

    this.socket = io({
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: this.maxReconnectAttempts,
    });

    this._setupEventHandlers();
  }

  /**
   * Configura los manejadores de eventos del socket.
   * @private
   */
  _setupEventHandlers() {
    // Evento: Conexión exitosa
    this.socket.on('connect', () => {
      console.log('WebSocket conectado');
      this.connected = true;
      this.reconnectAttempts = 0;
      this._updateConnectionStatus('Conectado', 'success');
      this._notifySubscribers('connected', {});
    });

    // Evento: Desconexión
    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket desconectado:', reason);
      this.connected = false;
      this._updateConnectionStatus('Desconectado', 'secondary');
      this._notifySubscribers('disconnected', { reason });
    });

    // Evento: Error de conexión
    this.socket.on('connect_error', (error) => {
      console.error('Error de conexión:', error);
      this.reconnectAttempts++;

      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        this._updateConnectionStatus('Error', 'danger');
        this._notifySubscribers('connection_error', { error });
      }
    });

    // Evento: Mensaje de confirmación
    this.socket.on('connected', (data) => {
      console.log('Mensaje del servidor:', data.message);
    });

    // Evento: Actualización de cuenta
    this.socket.on('account_update', (data) => {
      this._notifySubscribers('account_update', data);
    });

    // Evento: Actualización de posiciones
    this.socket.on('positions_update', (data) => {
      this._notifySubscribers('positions_update', data);
    });

    // Evento: Actualización de cotización
    this.socket.on('quote_update', (data) => {
      this._notifySubscribers('quote_update', data);
    });

    // Evento: Orden creada
    this.socket.on('order_created', (data) => {
      this._notifySubscribers('order_created', data);
      showNotification('Orden creada exitosamente', 'success');
    });

    // Evento: Orden cancelada
    this.socket.on('order_cancelled', (data) => {
      this._notifySubscribers('order_cancelled', data);
      showNotification('Orden cancelada', 'info');
    });

    // Evento: Swing trade creado
    this.socket.on('swing_trade_created', (data) => {
      this._notifySubscribers('swing_trade_created', data);
      showNotification('Swing trade creado exitosamente', 'success');
    });

    // Evento: Error del servidor
    this.socket.on('error', (data) => {
      console.error('Error del servidor:', data.message);
      showNotification('Error: ' + data.message, 'danger');
    });

    // Evento: Suscripción exitosa
    this.socket.on('subscribed', (data) => {
      console.log('Suscrito a:', data.symbol);
    });
  }

  /**
   * Actualiza el estado de conexión en la UI.
   * @private
   * @param {string} text - Texto del estado
   * @param {string} status - Clase de Bootstrap (success, danger, secondary)
   */
  _updateConnectionStatus(text, status) {
    const statusElement = document.getElementById('connection-status');
    if (statusElement) {
      statusElement.textContent = text;
      statusElement.className = `badge bg-${status} me-3`;
    }
  }

  /**
   * Notifica a todos los suscriptores de un evento.
   * @private
   * @param {string} event - Nombre del evento
   * @param {Object} data - Datos del evento
   */
  _notifySubscribers(event, data) {
    if (this.subscribers[event]) {
      this.subscribers[event].forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error en subscriber de ${event}:`, error);
        }
      });
    }
  }

  /**
   * Suscribe un callback a un evento específico.
   * @param {string} event - Nombre del evento
   * @param {Function} callback - Función a ejecutar cuando ocurra el evento
   */
  subscribe(event, callback) {
    if (!this.subscribers[event]) {
      this.subscribers[event] = [];
    }
    this.subscribers[event].push(callback);
  }

  /**
   * Emite un evento al servidor.
   * @param {string} event - Nombre del evento
   * @param {Object} data - Datos a enviar
   */
  emit(event, data = {}) {
    if (!this.connected) {
      console.warn('Socket no conectado. No se puede emitir evento:', event);
      return;
    }
    this.socket.emit(event, data);
  }

  /**
   * Suscribe a actualizaciones de un símbolo.
   * @param {string} symbol - Símbolo del activo
   */
  subscribeToSymbol(symbol) {
    this.emit('subscribe_symbol', { symbol: symbol.toUpperCase() });
  }

  /**
   * Solicita actualización de la cuenta.
   */
  requestAccountUpdate() {
    this.emit('request_account_update');
  }

  /**
   * Solicita actualización de posiciones.
   */
  requestPositionsUpdate() {
    this.emit('request_positions_update');
  }
}

// Instancia global del cliente WebSocket
const wsClient = new WebSocketClient();

/**
 * Muestra una notificación toast.
 * @param {string} message - Mensaje a mostrar
 * @param {string} type - Tipo de notificación (success, danger, info, warning)
 */
function showNotification(message, type = 'info') {
  const toastElement = document.getElementById('notification-toast');
  const toastBody = document.getElementById('toast-message');

  if (toastElement && toastBody) {
    // Actualizar mensaje
    toastBody.textContent = message;

    // Actualizar color según tipo
    const toast = bootstrap.Toast.getOrCreateInstance(toastElement);
    const toastHeader = toastElement.querySelector('.toast-header');

    // Remover clases previas
    toastHeader.classList.remove(
      'bg-success',
      'bg-danger',
      'bg-info',
      'bg-warning',
      'text-white'
    );

    // Agregar clase según tipo
    if (type === 'success') {
      toastHeader.classList.add('bg-success', 'text-white');
    } else if (type === 'danger') {
      toastHeader.classList.add('bg-danger', 'text-white');
    } else if (type === 'warning') {
      toastHeader.classList.add('bg-warning');
    } else {
      toastHeader.classList.add('bg-info', 'text-white');
    }

    // Mostrar toast
    toast.show();
  }
}

// Inicializar conexión cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  wsClient.connect();
});
