"""缓存服务

负责：
- 任务状态缓存
- 热点商品缓存
- 通用键值缓存

轻量模式：使用进程内字典（无 Redis 依赖），重启后失效。
完整模式：使用 Redis。
"""

import json
import time
from typing import Optional, Any

from app.config import settings

# Redis 客户端单例（完整模式）
_pool = None

# 进程内缓存（轻量模式）
_memory_cache: dict[str, tuple[Any, float]] = {}  # key -> (value, expire_ts)


def get_redis():
    """获取 Redis 客户端单例（完整模式）"""
    global _pool
    if _pool is None:
        import redis
        _pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
    return redis.Redis(connection_pool=_pool)


def cache_set(key: str, value: Any, expire: int = 300) -> bool:
    """写入缓存（自动 JSON 序列化）"""
    if settings.LIGHTWEIGHT:
        _memory_cache[key] = (json.dumps(value, ensure_ascii=False, default=str), time.time() + expire)
        return True
    client = get_redis()
    return client.setex(key, expire, json.dumps(value, ensure_ascii=False, default=str))


def cache_get(key: str) -> Optional[Any]:
    """读取缓存（自动 JSON 反序列化）"""
    if settings.LIGHTWEIGHT:
        item = _memory_cache.get(key)
        if item is None:
            return None
        val, expire_ts = item
        if expire_ts < time.time():
            _memory_cache.pop(key, None)
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    client = get_redis()
    val = client.get(key)
    if val is None:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return val


def cache_delete(key: str) -> bool:
    """删除缓存"""
    if settings.LIGHTWEIGHT:
        return _memory_cache.pop(key, None) is not None
    client = get_redis()
    return client.delete(key) > 0


def cache_goods(barcode: str, goods_data: dict, expire: int = 600):
    """缓存热点商品"""
    cache_set(f"goods:{barcode}", goods_data, expire)


def get_cached_goods(barcode: str) -> Optional[dict]:
    """获取缓存商品"""
    return cache_get(f"goods:{barcode}")


def invalidate_goods(barcode: str):
    """商品变更时失效缓存"""
    cache_delete(f"goods:{barcode}")


def set_task_progress(task_id: str, progress: dict, expire: int = 86400):
    """设置导入任务进度缓存"""
    cache_set(f"task:{task_id}", progress, expire)


def get_task_progress(task_id: str) -> Optional[dict]:
    """获取导入任务进度"""
    return cache_get(f"task:{task_id}")
