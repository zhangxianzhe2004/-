"""Celery 应用实例

任务队列：Redis 作为 broker 和 result backend
用于异步处理大批量图片向量化任务，避免接口超时。

轻量模式（Celery/Redis 不可用）：导入任务改为同步执行，不依赖本模块。
"""

from app.config import settings

CELERY_AVAILABLE = False
celery_app = None

try:
    from celery import Celery

    celery_app = Celery(
        "goods_search",
        broker=settings.CELERY_BROKER,
        backend=settings.CELERY_BACKEND,
        include=["app.tasks.import_tasks"],
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=False,
        worker_concurrency=4,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        result_expires=86400,
        task_time_limit=3600,
        task_soft_time_limit=3000,
    )
    CELERY_AVAILABLE = True
except Exception as e:
    print(f"[警告] Celery 不可用，导入任务将同步执行：{e}")
