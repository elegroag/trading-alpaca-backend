# 📈 Trading Swing App - Flask + WebSocket + Alpaca API

Backend API profesional para trading swing desarrollado con Flask, WebSocket e integración con Alpaca API. Sigue principios SOLID y patrones de diseño modernos.

## 🎯 Características

- **WebSocket**: Actualizaciones instantáneas de precios, posiciones y órdenes
- **Trading Swing**: Sistema completo con entry, take profit y stop loss
- **Gestión de Órdenes**: Creación, cancelación y monitoreo de órdenes
- **Arquitectura Limpia**: Código orientado a objetos con patrones SOLID
- **Paper Trading**: Integración con Alpaca Paper Trading API para practicar sin riesgo

## 🏗️ Arquitectura

La aplicación sigue una arquitectura en capas basada en principios SOLID:

```
┌──────────────────▼──────────────────────────┐
│           Controller Layer                   │
│        (Flask Routes + WebSocket)           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│            Service Layer                     │
│   (Trading Logic + Business Rules)          │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│          Repository Layer                    │
│        (Alpaca API Integration)             │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│            Data Layer                        │
│    (Models: Order, Position, Account)       │
└─────────────────────────────────────────────┘
```

## 📋 Requisitos Previos

- Python 3.8 o superior
- Cuenta en Alpaca Markets (Paper Trading)

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd proyecto_trading
```

### 2. Crear entorno virtual

```bash
python -m venv venv

# En Windows
venv\Scripts\activate

# En Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# Alpaca API Credentials (Paper Trading)
ALPACA_API_KEY=tu_api_key_aqui
ALPACA_SECRET_KEY=tu_secret_key_aqui
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Flask Configuration
SECRET_KEY=tu_clave_secreta_aleatoria_aqui
DEBUG=True
```

**Importante**: Para obtener tus credenciales de Alpaca:

1. Regístrate en [Alpaca Markets](https://alpaca.markets/)
2. Ve a tu dashboard
3. Genera tus API Keys en la sección de Paper Trading
4. Copia el API Key y Secret Key a tu archivo `.env`

### 5. Ejecutar la aplicación

```bash
python app.py
```

La API estará disponible en: `http://localhost:5080`

## 📁 Estructura del Proyecto

```
proyecto_trading/
│
├── app.py                          # Aplicación Flask principal
├── config.py                       # Configuración centralizada
├── requirements.txt                # Dependencias
├── .env                           # Variables de entorno (no incluir en git)
├── README.md                      # Este archivo
│
├── services/                      # Capa de servicios (Lógica de negocio)
│   ├── __init__.py
│   ├── alpaca_service.py         # Servicio para Alpaca API
│   └── trading_service.py        # Lógica de trading
│
├── models/                        # Modelos de datos
│   ├── __init__.py
│   └── order.py                  # Modelos: Order, Position, Account

└── sockets/                       # WebSocket handlers (server)
    └── ws_events.py
```

## 🔧 API REST Endpoints

### Account & Positions

```
GET /api/account           - Obtiene información de la cuenta
GET /api/positions         - Obtiene posiciones abiertas
GET /api/orders            - Obtiene órdenes abiertas
```

### Trading Operations

```
POST /api/orders           - Crea una nueva orden
POST /api/swing-trade      - Crea un swing trade completo
DELETE /api/orders/:id     - Cancela una orden
```

### Market Data

```
GET /api/quote/:symbol     - Obtiene cotización actual
GET /api/bars/:symbol      - Obtiene datos históricos
```

## 🔌 WebSocket Events

### Cliente → Servidor

```javascript
// Suscribirse a actualizaciones de un símbolo
socket.emit('subscribe_symbol', { symbol: 'AAPL' });

// Solicitar actualización de cuenta
socket.emit('request_account_update');

// Solicitar actualización de posiciones
socket.emit('request_positions_update');
```

### Servidor → Cliente

```javascript
// Orden creada
socket.on('order_created', (data) => { ... });

// Orden cancelada
socket.on('order_cancelled', (data) => { ... });

// Swing trade creado
socket.on('swing_trade_created', (data) => { ... });

// Actualización de cotización
socket.on('quote_update', (data) => { ... });

// Actualización de cuenta
socket.on('account_update', (data) => { ... });

// Actualización de posiciones
socket.on('positions_update', (data) => { ... });
```

## 🎨 Principios SOLID Implementados

### Single Responsibility Principle (SRP)

- Cada clase tiene una única responsabilidad
- `AlpacaService`: Solo comunicación con API
- `TradingService`: Solo lógica de trading
- `Config`: Solo configuración

### Open/Closed Principle (OCP)

- Servicios abiertos para extensión, cerrados para modificación
- Fácil agregar nuevos tipos de órdenes sin modificar código existente

### Liskov Substitution Principle (LSP)

- Los modelos pueden ser sustituidos por sus instancias
- Interfaces consistentes en toda la aplicación

### Interface Segregation Principle (ISP)

- APIs específicas y enfocadas
- No hay dependencias innecesarias

### Dependency Inversion Principle (DIP)

- Dependencias en abstracciones, no en implementaciones concretas
- Uso de instancias globales inyectables

## 🛡️ Seguridad

- **Variables de Entorno**: Credenciales nunca hardcodeadas
- **Validación de Datos**: Validación en cliente y servidor
- **Paper Trading**: Solo para práctica, no dinero real
- **HTTPS**: Recomendado para producción

## 🐛 Troubleshooting

### Error: "ALPACA_API_KEY no está configurada"

Solución: Asegúrate de tener el archivo `.env` con tus credenciales.

### Error: WebSocket desconectado

Solución: Verifica que el servidor Flask esté ejecutándose y que no haya firewalls bloqueando el puerto.

### Gráfico no carga datos

Solución: Verifica que el símbolo sea válido y que Alpaca tenga datos para ese símbolo.

## 📝 Notas Importantes

- Esta aplicación usa **Paper Trading de Alpaca** (dinero virtual)
- No uses credenciales de cuenta real
- Los precios son en tiempo real del mercado
- Respeta las horas de operación del mercado (9:30 AM - 4:00 PM ET)

## 🚀 Próximas Mejoras

- [ ] Autenticación de usuarios
- [ ] Base de datos para historial
- [ ] Backtesting de estrategias
- [ ] Alertas por email/SMS
- [ ] Análisis técnico avanzado
- [ ] Trading algorítmico

## 📄 Licencia

Este proyecto es solo para fines educativos.

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📞 Soporte

Para preguntas o problemas, abre un issue en el repositorio.

---

**Desarrollado con ❤️ siguiendo principios de Clean Code y SOLID**
