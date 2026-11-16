#!/bin/bash
set -e

echo "=================================================="
echo "♿ Starting InclusiCity Production Backend (Render Free Tier)"
echo "=================================================="

# Optional automatic admin initialization if credentials provided in environment
if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "🔑 Ensuring administrator account is initialized..."
    python seed_admin.py || echo "⚠️ Admin seeder returned non-zero, continuing startup..."
fi

# Optional automatic synthetic demo data seeder
if [ "${SEED_DEMO_DATA:-false}" = "true" ] || [ "${SEED_DEMO_DATA:-false}" = "1" ]; then
    echo "🌱 Seeding synthetic demonstration data and indexes..."
    python seed_demo_data.py || echo "⚠️ Demo seeder returned non-zero, continuing startup..."
fi

# Co-located zero-cost Celery execution
if [ "${CELERY_TASK_ALWAYS_EAGER:-false}" = "true" ] || [ "${CELERY_TASK_ALWAYS_EAGER:-false}" = "1" ]; then
    echo "ℹ️ Celery operating in in-process EAGER mode (zero background overhead)."
elif [ -n "$REDIS_URL" ]; then
    echo "🔄 Starting co-located Celery background worker (concurrency=1)..."
    celery -A celery_app.celery_app worker --loglevel=info --concurrency=1 &
else
    echo "⚠️ REDIS_URL not configured. Celery will execute tasks synchronously if needed."
fi

PORT_TO_USE="${PORT:-5000}"
echo "🌐 Launching Gunicorn with Eventlet on 0.0.0.0:${PORT_TO_USE}..."
exec gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:${PORT_TO_USE} --access-logfile - --error-logfile - app:app
