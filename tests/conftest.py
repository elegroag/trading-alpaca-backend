"""Configuración común de pytest: carga automática de variables desde .env.

Este archivo se ejecuta antes de los tests y asegura que
ALPACA_API_KEY, ALPACA_SECRET_KEY y el resto de variables definidas
en .env estén disponibles vía os.getenv.
"""

from pathlib import Path

from dotenv import load_dotenv


# Directorio raíz del proyecto (donde vive .env)
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Cargar variables de entorno desde .env si existe
load_dotenv(ENV_PATH)
