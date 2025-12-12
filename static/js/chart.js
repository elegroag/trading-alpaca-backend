/**
 * Manejo de gráficos con Chart.js.
 *
 * Implementa visualización de datos de precios históricos
 * con actualizaciones en tiempo real.
 */

/**
 * Clase para manejar el gráfico de precios.
 */
class PriceChart {
  /**
   * Constructor de la clase.
   * @param {string} canvasId - ID del elemento canvas
   */
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.chart = null;
    this.currentSymbol = null;
    this._initializeChart();
  }

  /**
   * Inicializa el gráfico con configuración por defecto.
   * @private
   */
  _initializeChart() {
    const ctx = this.canvas.getContext('2d');

    this.chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Precio',
            data: [],
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.1)',
            borderWidth: 2,
            fill: true,
            tension: 0,
            pointRadius: 0,
            pointHoverRadius: 5,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: 'index',
        },
        plugins: {
          legend: {
            display: true,
            labels: {
              color: '#ffffff',
            },
          },
          title: {
            display: true,
            text: 'Selecciona un símbolo para ver el gráfico',
            color: '#ffffff',
          },
          tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            titleColor: '#ffffff',
            bodyColor: '#ffffff',
            callbacks: {
              label: function (context) {
                let label = context.dataset.label || '';
                if (label) {
                  label += ': ';
                }
                if (context.parsed.y !== null) {
                  label += '$' + context.parsed.y.toFixed(2);
                }
                return label;
              },
            },
          },
        },
        scales: {
          x: {
            display: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.1)',
            },
            ticks: {
              color: '#ffffff',
              maxRotation: 0,
              minRotation: 0,
              autoSkip: true,
              maxTicksLimit: 8,
            },
          },
          y: {
            display: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.1)',
            },
            ticks: {
              color: '#ffffff',
              callback: function (value) {
                return '$' + value.toFixed(2);
              },
            },
          },
        },
      },
    });
  }

  /**
   * Carga datos históricos de un símbolo.
   * @param {string} symbol - Símbolo del activo
   * @param {string} timeframe - Marco temporal ('1Min', '5Min', '1H', '1D')
   * @param {number} limit - Número de barras
   */
  async loadData(symbol, timeframe = '1D', limit = 100) {
    try {
      this.currentSymbol = symbol.toUpperCase();

      // Mostrar estado de carga
      this.chart.options.plugins.title.text = `Cargando ${this.currentSymbol}...`;
      this.chart.update();

      // Obtener datos
      const response = await tradingAPI.getBars(
        this.currentSymbol,
        timeframe,
        limit
      );
      let bars = response.data;

      if (!bars || bars.length === 0) {
        this.chart.options.plugins.title.text = `No hay datos disponibles para ${this.currentSymbol}`;
        this.chart.data.labels = [];
        this.chart.data.datasets[0].data = [];
        this.chart.update();
        return;
      }

      bars = bars
        .slice()
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

      // Procesar datos
      const labels = bars.map((bar) => {
        const date = new Date(bar.timestamp);
        return this._formatDate(date, timeframe);
      });

      const prices = bars.map((bar) => bar.close);

      // Actualizar gráfico
      this.chart.data.labels = labels;
      this.chart.data.datasets[0].data = prices;
      this.chart.data.datasets[0].label = `${this.currentSymbol} - Precio de Cierre`;
      this.chart.options.plugins.title.text = `${this.currentSymbol} - Últimos ${bars.length} períodos (${timeframe})`;

      // Determinar color según tendencia
      const firstPrice = prices[0];
      const lastPrice = prices[prices.length - 1];
      if (lastPrice >= firstPrice) {
        this.chart.data.datasets[0].borderColor = 'rgb(75, 192, 75)';
        this.chart.data.datasets[0].backgroundColor = 'rgba(75, 192, 75, 0.1)';
      } else {
        this.chart.data.datasets[0].borderColor = 'rgb(255, 99, 99)';
        this.chart.data.datasets[0].backgroundColor = 'rgba(255, 99, 99, 0.1)';
      }

      this.chart.update();

      // Suscribirse a actualizaciones en tiempo real
      wsClient.subscribeToSymbol(this.currentSymbol);

      showNotification(`Gráfico de ${this.currentSymbol} cargado`, 'success');
    } catch (error) {
      console.error('Error al cargar datos del gráfico:', error);
      this.chart.options.plugins.title.text = `Error al cargar ${this.currentSymbol}`;
      this.chart.update();
      showNotification('Error al cargar gráfico: ' + error.message, 'danger');
    }
  }

  /**
   * Formatea una fecha según el marco temporal.
   * @private
   * @param {Date} date - Fecha a formatear
   * @param {string} timeframe - Marco temporal
   * @returns {string} Fecha formateada
   */
  _formatDate(date, timeframe) {
    const options = {
      hour12: false,
    };

    if (timeframe.includes('Min') || timeframe.includes('H')) {
      // Para intradiario, mostrar hora
      return date.toLocaleString('es-ES', {
        ...options,
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } else {
      // Para diario, mostrar solo fecha
      return date.toLocaleDateString('es-ES', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    }
  }

  /**
   * Actualiza un punto de datos en tiempo real.
   * @param {number} newPrice - Nuevo precio
   */
  updateRealtime(newPrice) {
    if (!this.chart || !this.chart.data.datasets[0].data.length) {
      return;
    }

    // Actualizar último punto
    const data = this.chart.data.datasets[0].data;
    data[data.length - 1] = newPrice;

    // Actualizar color según cambio
    const previousPrice = data[data.length - 2];
    if (newPrice >= previousPrice) {
      this.chart.data.datasets[0].borderColor = 'rgb(75, 192, 75)';
      this.chart.data.datasets[0].backgroundColor = 'rgba(75, 192, 75, 0.1)';
    } else {
      this.chart.data.datasets[0].borderColor = 'rgb(255, 99, 99)';
      this.chart.data.datasets[0].backgroundColor = 'rgba(255, 99, 99, 0.1)';
    }

    this.chart.update('none'); // Update sin animación
  }

  /**
   * Agrega un nuevo punto de datos.
   * @param {string} label - Etiqueta temporal
   * @param {number} price - Precio
   */
  addDataPoint(label, price) {
    if (!this.chart) {
      return;
    }

    this.chart.data.labels.push(label);
    this.chart.data.datasets[0].data.push(price);

    // Mantener solo los últimos 100 puntos
    if (this.chart.data.labels.length > 100) {
      this.chart.data.labels.shift();
      this.chart.data.datasets[0].data.shift();
    }

    this.chart.update();
  }

  /**
   * Limpia el gráfico.
   */
  clear() {
    if (!this.chart) {
      return;
    }

    this.chart.data.labels = [];
    this.chart.data.datasets[0].data = [];
    this.chart.options.plugins.title.text =
      'Selecciona un símbolo para ver el gráfico';
    this.currentSymbol = null;
    this.chart.update();
  }
}

// Instancia global del gráfico
let priceChart = null;

// Event Listeners cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  // Inicializar gráfico
  priceChart = new PriceChart('price-chart');

  // Botón para cargar gráfico
  const loadChartBtn = document.getElementById('load-chart');
  const chartSymbolInput = document.getElementById('chart-symbol');
  const chartTimeframeSelect = document.getElementById('chart-timeframe');

  loadChartBtn?.addEventListener('click', () => {
    const symbol = chartSymbolInput.value.trim().toUpperCase();
    const timeframe = chartTimeframeSelect?.value || '1D';
    if (symbol) {
      priceChart.loadData(symbol, timeframe);
    } else {
      showNotification('Ingresa un símbolo válido', 'warning');
    }
  });

  // Enter en el input de símbolo
  chartSymbolInput?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      loadChartBtn.click();
    }
  });

  // Suscribirse a actualizaciones de cotización en tiempo real
  wsClient.subscribe('quote_update', (data) => {
    if (priceChart && priceChart.currentSymbol === data.symbol) {
      priceChart.updateRealtime(data.price);
    }
  });

  // Cargar símbolo por defecto (AAPL)
  setTimeout(() => {
    chartSymbolInput.value = 'AAPL';
    const initialTimeframe = chartTimeframeSelect?.value || '1D';
    priceChart.loadData('AAPL', initialTimeframe);
  }, 1000);
});
