# ==========================================
# InclusiCity Backend - Production Dockerfile
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final production image
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH" \
    PORT=5000

COPY --from=builder /root/.local /root/.local
COPY . /app

# Ensure uploads directory exists
RUN mkdir -p /app/uploads/helpers

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Production Gunicorn Eventlet Worker for Flask-SocketIO
CMD ["sh", "-c", "gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:${PORT} --access-logfile - --error-logfile - app:app"]
