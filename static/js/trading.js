/**
 * Lógica de trading y actualización de UI.
 *
 * Maneja la interacción con la API REST y actualiza la interfaz
 * con información de cuenta, posiciones y órdenes.
 */

/**
 * Clase para manejar operaciones de API.
 */
class TradingAPI {
  /**
   * Constructor de la clase.
   */
  constructor() {
    this.baseURL = window.location.origin;
  }

  /**
   * Realiza una petición HTTP.
   * @private
   * @param {string} endpoint - Endpoint de la API
   * @param {Object} options - Opciones de fetch
   * @returns {Promise<Object>} Respuesta de la API
   */
  async _request(endpoint, options = {}) {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Error en la petición');
      }

      return data;
    } catch (error) {
      console.error('Error en petición:', error);
      throw error;
    }
  }

  /**
   * Obtiene información de la cuenta.
   * @returns {Promise<Object>} Información de la cuenta
   */
  async getAccount() {
    return this._request('/api/account');
  }

  /**
   * Obtiene posiciones abiertas.
   * @returns {Promise<Object>} Lista de posiciones
   */
  async getPositions() {
    return this._request('/api/positions');
  }

  /**
   * Obtiene órdenes abiertas.
   * @returns {Promise<Object>} Lista de órdenes
   */
  async getOrders() {
    return this._request('/api/orders');
  }

  /**
   * Crea una nueva orden.
   * @param {Object} orderData - Datos de la orden
   * @returns {Promise<Object>} Orden creada
   */
  async createOrder(orderData) {
    return this._request('/api/orders', {
      method: 'POST',
      body: JSON.stringify(orderData),
    });
  }

  /**
   * Crea un swing trade.
   * @param {Object} tradeData - Datos del swing trade
   * @returns {Promise<Object>} Trade creado
   */
  async createSwingTrade(tradeData) {
    return this._request('/api/swing-trade', {
      method: 'POST',
      body: JSON.stringify(tradeData),
    });
  }

  /**
   * Cancela una orden.
   * @param {string} orderId - ID de la orden
   * @returns {Promise<Object>} Resultado
   */
  async cancelOrder(orderId) {
    return this._request(`/api/orders/${orderId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Obtiene cotización de un símbolo.
   * @param {string} symbol - Símbolo del activo
   * @returns {Promise<Object>} Cotización
   */
  async getQuote(symbol) {
    return this._request(`/api/quote/${symbol}`);
  }

  /**
   * Obtiene barras históricas.
   * @param {string} symbol - Símbolo del activo
   * @param {string} timeframe - Marco temporal
   * @param {number} limit - Número de barras
   * @returns {Promise<Object>} Barras históricas
   */
  async getBars(symbol, timeframe = '1D', limit = 100) {
    return this._request(
      `/api/bars/${symbol}?timeframe=${timeframe}&limit=${limit}`
    );
  }

  /**
   * Ejecuta el escaneo de la estrategia swing.
   * @param {string[]} tickers - Lista de símbolos
   * @param {boolean} execute - Si debe enviar órdenes o solo simular
   * @returns {Promise<Object>} Resumen por símbolo
   */
  async swingScan(tickers = [], execute = false) {
    const payload = { execute };
    if (tickers && tickers.length) {
      payload.tickers = tickers;
    }
    return this._request('/api/swing-scan', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}

// Instancia global de la API
const tradingAPI = new TradingAPI();

/**
 * Actualiza la información de la cuenta en la UI.
 */
async function updateAccountInfo() {
  try {
    const response = await tradingAPI.getAccount();
    const account = response.data;

    const accountHTML = `
            <div class="row g-2">
                <div class="col-12">
                    <div class="d-flex justify-content-between">
                        <span class="text-muted">Cuenta:</span>
                        <strong>${account.account_number}</strong>
                    </div>
                </div>
                <div class="col-12">
                    <div class="d-flex justify-content-between">
                        <span class="text-muted">Estado:</span>
                        <span class="badge bg-success">${account.status}</span>
                    </div>
                </div>
                <div class="col-12"><hr class="border-secondary"></div>
                <div class="col-12">
                    <div class="d-flex justify-content-between">
                        <span class="text-muted">Efectivo:</span>
                        <strong class="text-success">$${parseFloat(
                          account.cash
                        ).toLocaleString('en-US', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}</strong>
                    </div>
                </div>
                <div class="col-12">
                    <div class="d-flex justify-content-between">
                        <span class="text-muted">Poder de Compra:</span>
                        <strong class="text-info">$${parseFloat(
                          account.buying_power
                        ).toLocaleString('en-US', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}</strong>
                    </div>
                </div>
                <div class="col-12">
                    <div class="d-flex justify-content-between">
                        <span class="text-muted">Valor Portafolio:</span>
                        <strong class="text-warning">$${parseFloat(
                          account.portfolio_value
                        ).toLocaleString('en-US', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}</strong>
                    </div>
                </div>
                <div class="col-12">
                    <div class="d-flex justify-content-between">
                        <span class="text-muted">Capital Total:</span>
                        <strong class="text-primary">$${parseFloat(
                          account.equity
                        ).toLocaleString('en-US', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}</strong>
                    </div>
                </div>
            </div>
        `;

    document.getElementById('account-info').innerHTML = accountHTML;
  } catch (error) {
    console.error('Error al actualizar cuenta:', error);
    document.getElementById('account-info').innerHTML = `
            <div class="alert alert-danger mb-0">
                Error al cargar información de la cuenta
            </div>
        `;
  }
}

/**
 * Actualiza las posiciones abiertas en la UI.
 */
async function updatePositions() {
  try {
    const response = await tradingAPI.getPositions();
    const positions = response.data;

    if (positions.length === 0) {
      document.getElementById('positions-list').innerHTML = `
                <div class="alert alert-info mb-0">
                    No hay posiciones abiertas
                </div>
            `;
      return;
    }

    const positionsHTML = positions
      .map((pos) => {
        const plClass =
          parseFloat(pos.unrealized_pl) >= 0 ? 'text-success' : 'text-danger';
        const plSign = parseFloat(pos.unrealized_pl) >= 0 ? '+' : '';

        return `
                <div class="card bg-black border-secondary mb-2">
                    <div class="card-body p-3">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="mb-0 text-info">${pos.symbol}</h6>
                            <span class="badge bg-primary">${
                              pos.qty
                            } acciones</span>
                        </div>
                        <div class="row g-2 small">
                            <div class="col-6">
                                <div class="text-muted">Precio Entrada:</div>
                                <div>$${parseFloat(pos.avg_entry_price).toFixed(
                                  2
                                )}</div>
                            </div>
                            <div class="col-6">
                                <div class="text-muted">Precio Actual:</div>
                                <div>$${parseFloat(pos.current_price).toFixed(
                                  2
                                )}</div>
                            </div>
                            <div class="col-6">
                                <div class="text-muted">Valor Mercado:</div>
                                <div>$${parseFloat(
                                  pos.market_value
                                ).toLocaleString('en-US', {
                                  minimumFractionDigits: 2,
                                })}</div>
                            </div>
                            <div class="col-6">
                                <div class="text-muted">P&L:</div>
                                <div class="${plClass}">
                                    ${plSign}$${parseFloat(
          pos.unrealized_pl
        ).toFixed(2)} 
                                    (${plSign}${(
          parseFloat(pos.unrealized_plpc) * 100
        ).toFixed(2)}%)
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
      })
      .join('');

    document.getElementById('positions-list').innerHTML = positionsHTML;
  } catch (error) {
    console.error('Error al actualizar posiciones:', error);
    document.getElementById('positions-list').innerHTML = `
            <div class="alert alert-danger mb-0">
                Error al cargar posiciones
            </div>
        `;
  }
}

/**
 * Actualiza las órdenes abiertas en la UI.
 */
async function updateOrders() {
  try {
    const response = await tradingAPI.getOrders();
    const orders = response.data;

    if (orders.length === 0) {
      document.getElementById('orders-list').innerHTML = `
                <div class="alert alert-info mb-0">
                    No hay órdenes abiertas
                </div>
            `;
      return;
    }

    const ordersHTML = orders
      .map((order) => {
        const sideClass = order.side === 'buy' ? 'success' : 'danger';
        const sideText = order.side === 'buy' ? 'Compra' : 'Venta';

        return `
                <div class="card bg-black border-secondary mb-2">
                    <div class="card-body p-3">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="mb-0 text-info">${order.symbol}</h6>
                            <div>
                                <span class="badge bg-${sideClass} me-1">${sideText}</span>
                                <button class="btn btn-sm btn-outline-danger" onclick="cancelOrderHandler('${
                                  order.order_id
                                }')">
                                    ✕
                                </button>
                            </div>
                        </div>
                        <div class="row g-2 small">
                            <div class="col-6">
                                <div class="text-muted">Cantidad:</div>
                                <div>${order.qty}</div>
                            </div>
                            <div class="col-6">
                                <div class="text-muted">Tipo:</div>
                                <div>${order.order_type}</div>
                            </div>
                            ${
                              order.limit_price
                                ? `
                            <div class="col-6">
                                <div class="text-muted">Precio Límite:</div>
                                <div>$${parseFloat(order.limit_price).toFixed(
                                  2
                                )}</div>
                            </div>
                            `
                                : ''
                            }
                            <div class="col-6">
                                <div class="text-muted">Estado:</div>
                                <div><span class="badge bg-warning">${
                                  order.status
                                }</span></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
      })
      .join('');

    document.getElementById('orders-list').innerHTML = ordersHTML;
  } catch (error) {
    console.error('Error al actualizar órdenes:', error);
    document.getElementById('orders-list').innerHTML = `
            <div class="alert alert-danger mb-0">
                Error al cargar órdenes
            </div>
        `;
  }
}

/**
 * Manejador para cancelar una orden.
 * @param {string} orderId - ID de la orden
 */
async function cancelOrderHandler(orderId) {
  if (!confirm('¿Estás seguro de cancelar esta orden?')) {
    return;
  }

  try {
    await tradingAPI.cancelOrder(orderId);
    showNotification('Orden cancelada exitosamente', 'success');
    updateOrders();
  } catch (error) {
    showNotification('Error al cancelar orden: ' + error.message, 'danger');
  }
}

/**
 * Actualiza todos los datos.
 */
async function refreshAll() {
  await Promise.all([updateAccountInfo(), updatePositions(), updateOrders()]);
}

// Event Listeners cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  // Cargar datos iniciales
  refreshAll();

  // Botón de refresh global
  const refreshBtn = document.getElementById('refresh-all');
  refreshBtn?.addEventListener('click', async () => {
    if (refreshBtn.disabled) return;
    const originalHtml = refreshBtn.innerHTML;
    refreshBtn.disabled = true;
    refreshBtn.innerHTML =
      '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Actualizando...';
    try {
      await refreshAll();
      showNotification('Datos actualizados', 'info');
    } catch (error) {
      showNotification('Error al actualizar datos: ' + error.message, 'danger');
    } finally {
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = originalHtml;
    }
  });

  // Formulario de orden
  const orderForm = document.getElementById('order-form');
  const orderTypeSelect = document.getElementById('order_type');
  const limitPriceGroup = document.getElementById('limit-price-group');

  // Mostrar/ocultar precio límite según tipo de orden
  orderTypeSelect?.addEventListener('change', (e) => {
    if (e.target.value === 'limit') {
      limitPriceGroup.style.display = 'block';
      document.getElementById('limit_price').required = true;
    } else {
      limitPriceGroup.style.display = 'none';
      document.getElementById('limit_price').required = false;
    }
  });

  // Submit del formulario de orden
  orderForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const orderData = {
      symbol: document.getElementById('symbol').value.toUpperCase(),
      qty: parseFloat(document.getElementById('qty').value),
      side: document.getElementById('side').value,
      order_type: document.getElementById('order_type').value,
    };

    if (orderData.order_type === 'limit') {
      orderData.limit_price = parseFloat(
        document.getElementById('limit_price').value
      );
    }

    const submitBtn = orderForm.querySelector('button[type="submit"]');
    const originalHtml = submitBtn ? submitBtn.innerHTML : null;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Enviando...';
    }

    try {
      await tradingAPI.createOrder(orderData);
      showNotification('Orden creada exitosamente', 'success');
      orderForm.reset();
      limitPriceGroup.style.display = 'none';
      refreshAll();
    } catch (error) {
      showNotification('Error: ' + error.message, 'danger');
    } finally {
      if (submitBtn && originalHtml !== null) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalHtml;
      }
    }
  });

  // Estrategia swing automática (escaneo)
  const swingScanForm = document.getElementById('swing-scan-form');
  const swingScanResults = document.getElementById('swing-scan-results');

  swingScanForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const tickersInput = document.getElementById('swing-scan-tickers');
    const executeCheckbox = document.getElementById('swing-scan-execute');
    const raw = tickersInput?.value.trim() || '';
    const execute = !!executeCheckbox?.checked;

    const tickers = raw
      ? raw
          .split(',')
          .map((t) => t.trim().toUpperCase())
          .filter((t) => t.length > 0)
      : [];

    const submitBtn = document.getElementById('swing-scan-btn');
    const originalHtml = submitBtn ? submitBtn.innerHTML : null;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>' +
        (execute ? 'Escaneando y ejecutando...' : 'Escaneando estrategia...');
    }

    try {
      const response = await tradingAPI.swingScan(tickers, execute);
      const results = response.data || [];

      if (!results.length) {
        swingScanResults.innerHTML =
          '<div class="text-muted">No se obtuvieron resultados.</div>';
      } else {
        const html = results
          .map((r) => {
            if (!r.has_signal) {
              return `
                <div class="border-bottom border-secondary py-1">
                  <strong>${r.symbol}</strong>:
                  <span class="text-muted">${
                    r.reason || 'Sin señal de entrada'
                  }</span>
                </div>
              `;
            }

            const executed = r.order_id ? '✅ Orden enviada' : '🔍 Solo señal';
            return `
              <div class="border-bottom border-secondary py-1">
                <strong>${r.symbol}</strong> - qty ${r.qty} @ $${Number(
              r.entry_price
            ).toFixed(2)}
                <div class="text-muted">
                  SL: $${Number(r.stop_price).toFixed(2)} · TP: $${Number(
              r.take_profit_price
            ).toFixed(2)} · ${executed}
                </div>
              </div>
            `;
          })
          .join('');

        swingScanResults.innerHTML = html;
      }

      showNotification(
        execute
          ? 'Estrategia swing ejecutada. Revisa las órdenes abiertas.'
          : 'Escaneo de estrategia swing completado.',
        'info'
      );

      if (execute) {
        refreshAll();
      }
    } catch (error) {
      console.error('Error en swing-scan:', error);
      swingScanResults.innerHTML = `
        <div class="text-danger">
          Error al ejecutar estrategia swing: ${
            error.message || 'Error desconocido'
          }
        </div>
      `;
      showNotification(
        'Error al ejecutar estrategia swing: ' + (error.message || ''),
        'danger'
      );
    } finally {
      if (submitBtn && originalHtml !== null) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalHtml;
      }
    }
  });

  // Formulario de swing trade
  const swingForm = document.getElementById('swing-trade-form');
  swingForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const tradeData = {
      symbol: document.getElementById('swing-symbol').value.toUpperCase(),
      qty: parseFloat(document.getElementById('swing-qty').value),
      entry_price: parseFloat(document.getElementById('entry-price').value),
      take_profit_price: parseFloat(document.getElementById('tp-price').value),
      stop_loss_price: parseFloat(document.getElementById('sl-price').value),
    };

    const submitBtn = swingForm.querySelector('button[type="submit"]');
    const originalHtml = submitBtn ? submitBtn.innerHTML : null;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Enviando...';
    }

    try {
      await tradingAPI.createSwingTrade(tradeData);
      showNotification('Swing trade creado exitosamente', 'success');
      swingForm.reset();
      refreshAll();
    } catch (error) {
      showNotification('Error: ' + error.message, 'danger');
    } finally {
      if (submitBtn && originalHtml !== null) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalHtml;
      }
    }
  });

  // Suscribirse a eventos de WebSocket
  wsClient.subscribe('connected', refreshAll);
  wsClient.subscribe('order_created', updateOrders);
  wsClient.subscribe('order_cancelled', updateOrders);
  wsClient.subscribe('account_update', (data) => {
    // Actualizar con datos del WebSocket si es necesario
    console.log('Cuenta actualizada vía WebSocket', data);
  });

  // Auto-refresh cada 30 segundos
  setInterval(refreshAll, 30000);
});
