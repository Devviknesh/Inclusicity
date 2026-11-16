import os
import ssl
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Configure Celery instance
celery_app = Celery(
    "inclusicity",
    broker=redis_url,
    backend=redis_url,
)

# Explicit task registration
from utils import email_tasks  # noqa: F401

celery_config = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "broker_connection_retry_on_startup": True,
    # Zero-cost & Upstash free-tier optimizations
    "task_always_eager": os.getenv("CELERY_TASK_ALWAYS_EAGER", "False").lower() in ("true", "1"),
    "result_expires": 3600,  # Expire task metadata after 1 hour to prevent Redis memory growth
    "task_time_limit": 30,   # Prevent hung tasks on free containers
    "task_soft_time_limit": 20,
}

# Upstash Redis TLS (rediss://) support
if redis_url.startswith("rediss://"):
    ssl_options = {
        "ssl_cert_reqs": ssl.CERT_NONE  # Upstash managed TLS
    }
    celery_config["broker_use_ssl"] = ssl_options
    celery_config["redis_backend_use_ssl"] = ssl_options

celery_app.conf.update(**celery_config)
