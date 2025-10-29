FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copiar dependencias primero
COPY requirements.txt ./
RUN pip install --upgrade pip wheel \
    && pip install -r requirements.txt \
    && pip install gunicorn \
    && rm -rf /root/.cache/pip

# Copiar el resto del código
COPY . .

# Exponer puerto definido en la variable de entorno PORT
EXPOSE 5000

# Ejecutar Gunicorn usando la variable PORT
CMD gunicorn -b 0.0.0.0:${PORT:-5000} app:app