"""向量库服务

负责：
- 初始化向量集合（图像向量 / 文本向量）
- 插入向量（绑定 barcode）
- 向量检索（返回 TopN + 距离分数）
- 删除向量

轻量模式 / Milvus 不可用：降级为进程内内存向量库（暴力余弦检索）。
完整模式：使用 Milvus-Lite。
"""

import atexit
import json
import math
import os
import threading
from typing import Optional

from app.config import settings

# Milvus 客户端单例
_client = None
_milvus_available: Optional[bool] = None  # None=未检测, True/False

# 内存向量库（降级模式）
_memory_vectors: dict[str, dict[str, dict]] = {}  # collection -> barcode -> {"vector": [...], "category": ""}
_memory_lock = threading.Lock()

# ---------- 内存向量库磁盘持久化（解决重启后向量丢失） ----------
_PERSIST_PATH = os.path.join(os.path.dirname(settings.MILVUS_URI) or "data", "memory_vectors.json")
_save_timer: Optional[threading.Timer] = None


def _load_memory():
    """启动时从磁盘恢复内存向量库"""
    global _memory_vectors
    if os.path.exists(_PERSIST_PATH):
        try:
            with open(_PERSIST_PATH, "r", encoding="utf-8") as f:
                _memory_vectors = json.load(f)
            total = sum(len(v) for v in _memory_vectors.values())
            print(f"[向量库] 内存向量库已从磁盘恢复：{total} 条向量")
        except Exception as e:
            print(f"[警告] 内存向量库恢复失败（使用空库）：{e}")


def _save_memory_now():
    """立即把内存向量库写入磁盘"""
    try:
        with _memory_lock:
            data = json.dumps(_memory_vectors, ensure_ascii=False)
        os.makedirs(os.path.dirname(_PERSIST_PATH) or ".", exist_ok=True)
        with open(_PERSIST_PATH, "w", encoding="utf-8") as f:
            f.write(data)
    except Exception as e:
        print(f"[警告] 内存向量库保存失败：{e}")


def _schedule_save():
    """防抖保存：0.5 秒内多次写入合并为一次写盘"""
    global _save_timer
    if _save_timer:
        _save_timer.cancel()
    _save_timer = threading.Timer(0.5, _save_memory_now)
    _save_timer.daemon = True
    _save_timer.start()


# 模块加载时恢复数据；进程退出时兜底保存
_load_memory()
atexit.register(_save_memory_now)


def _try_init_milvus():
    """尝试初始化 Milvus，返回是否可用"""
    global _client, _milvus_available
    if _milvus_available is not None:
        return _milvus_available
    try:
        from pymilvus import MilvusClient, DataType
        db_path = settings.MILVUS_URI
        db_dir = os.path.dirname(db_path) or "."
        os.makedirs(db_dir, exist_ok=True)
        _client = MilvusClient(uri=db_path)
        _ensure_collections()
        _milvus_available = True
        print("[向量库] Milvus-Lite 初始化成功")
    except Exception as e:
        _milvus_available = False
        print(f"[警告] Milvus 不可用，降级为内存向量库：{e}")
    return _milvus_available


def get_client():
    """获取向量库客户端（Milvus 或 None）"""
    _try_init_milvus()
    return _client


def _ensure_collections():
    """确保图像向量集合和文本向量集合存在"""
    _ensure_one_collection(settings.MILVUS_COLLECTION_IMAGE, settings.MILVUS_DIM)
    _ensure_one_collection(settings.MILVUS_COLLECTION_TEXT, settings.MILVUS_TEXT_DIM)


def _ensure_one_collection(collection_name: str, dim: int):
    """创建单个向量集合（Milvus 模式）"""
    from pymilvus import DataType
    client = get_client()
    if client.has_collection(collection_name):
        return
    schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field("barcode", DataType.VARCHAR, is_primary=True, max_length=64)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field("category", DataType.VARCHAR, max_length=64)
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type=settings.MILVUS_INDEX_TYPE,
        metric_type=settings.MILVUS_METRIC_TYPE,
        params={"nlist": 128},
    )
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )


def insert_vector(collection_name: str, barcode: str, vector: list[float], category: str = ""):
    """插入（或覆盖）一条向量"""
    if _try_init_milvus():
        try:
            client = get_client()
            client.upsert(
                collection_name=collection_name,
                data=[{"barcode": barcode, "vector": vector, "category": category}],
            )
            return
        except Exception:
            # 兜底：先删后插
            try:
                delete_vector(collection_name, barcode)
                client.insert(
                    collection_name=collection_name,
                    data=[{"barcode": barcode, "vector": vector, "category": category}],
                )
                return
            except Exception as e:
                print(f"[向量库] Milvus 插入失败，降级内存：{e}")
    # 内存模式
    with _memory_lock:
        _memory_vectors.setdefault(collection_name, {})[barcode] = {
            "vector": vector, "category": category
        }
    _schedule_save()


def delete_vector(collection_name: str, barcode: str):
    """按 barcode 删除向量"""
    if _try_init_milvus() and _client is not None:
        try:
            client = get_client()
            client.delete(collection_name=collection_name, filter=f'barcode == "{barcode}"')
        except Exception as e:
            print(f"[向量库] 删除失败：{e}")
    with _memory_lock:
        _memory_vectors.get(collection_name, {}).pop(barcode, None)
    _schedule_save()


def delete_barcode_vectors(barcode: str):
    """删除某商品在图像和文本向量集合中的所有向量"""
    delete_vector(settings.MILVUS_COLLECTION_IMAGE, barcode)
    delete_vector(settings.MILVUS_COLLECTION_TEXT, barcode)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算余弦相似度"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return dot / (norm_a * norm_b)


def search_vectors(
    collection_name: str,
    query_vector: list[float],
    top_n: int = 10,
    category: Optional[str] = None,
) -> list[dict]:
    """向量检索

    Returns:
        [{"barcode": ..., "score": ...}, ...]  score 越高越相似（0~1）
    """
    if _try_init_milvus() and _client is not None:
        try:
            client = get_client()
            search_params = {"metric_type": settings.MILVUS_METRIC_TYPE, "params": {"nprobe": 16}}
            filter_expr = f'category == "{category}"' if category else None
            results = client.search(
                collection_name=collection_name,
                data=[query_vector],
                anns_field="vector",
                limit=top_n,
                search_params=search_params,
                filter=filter_expr,
                output_fields=["barcode"],
            )
            out = []
            if results and len(results) > 0:
                for hit in results[0]:
                    barcode = hit.get("entity", {}).get("barcode") or hit.get("barcode", "")
                    score = hit.get("distance", 0.0)
                    score = float(score) if score <= 1.0 else float(score) / 100.0
                    out.append({"barcode": barcode, "score": score})
            return out
        except Exception as e:
            print(f"[向量库] Milvus 检索失败，降级内存：{e}")

    # 内存模式：暴力余弦检索
    with _memory_lock:
        collection = _memory_vectors.get(collection_name, {})
        scored = []
        for barcode, data in collection.items():
            if category and data.get("category") != category:
                continue
            score = _cosine_similarity(query_vector, data["vector"])
            scored.append({"barcode": barcode, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


def insert_image_vector(barcode: str, vector: list[float], category: str = ""):
    """写入图像向量"""
    insert_vector(settings.MILVUS_COLLECTION_IMAGE, barcode, vector, category)


def insert_text_vector(barcode: str, vector: list[float], category: str = ""):
    """写入文本向量"""
    insert_vector(settings.MILVUS_COLLECTION_TEXT, barcode, vector, category)


def search_image_vectors(query_vector: list[float], top_n: int = 10, category: Optional[str] = None) -> list[dict]:
    """图像向量检索"""
    return search_vectors(settings.MILVUS_COLLECTION_IMAGE, query_vector, top_n, category)


def search_text_vectors(query_vector: list[float], top_n: int = 10, category: Optional[str] = None) -> list[dict]:
    """文本向量检索"""
    return search_vectors(settings.MILVUS_COLLECTION_TEXT, query_vector, top_n, category)


def count_vectors(collection_name: str) -> int:
    """统计集合中向量数量"""
    if _try_init_milvus() and _client is not None:
        try:
            stats = get_client().get_collection_stats(collection_name)
            return stats.get("row_count", 0)
        except Exception:
            pass
    with _memory_lock:
        return len(_memory_vectors.get(collection_name, {}))
