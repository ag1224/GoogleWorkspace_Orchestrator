from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "workspace_orchestrator",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    beat_schedule={
        "sync-all-users": {
            "task": "app.workers.tasks.sync_all_users",
            "schedule": crontab(minute=f"*/{settings.sync_interval_minutes}"),
        },
    },
)
