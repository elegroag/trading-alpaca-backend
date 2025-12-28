FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Dependencias del sistema requeridas
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-dejavu-core \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar solo dependencias primero (cache optimization)
COPY pyproject.toml uv.lock README.md ./

# Instalar uv y dependencias
RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache-dir -e .

# Copiar código fuente
COPY . .

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Exponer puerto
EXPOSE 5080

# Usar Gunicorn para producción
CMD ["uv", "run", "gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5080", "app:app"]