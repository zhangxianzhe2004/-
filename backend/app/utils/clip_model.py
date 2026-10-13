"""CLIP 图像向量 + BGE 文本向量模型加载与提取

本模块负责：
1. 加载中文 CLIP 模型（图像向量）
2. 加载 BGE 文本向量模型
3. 提供图像/文本向量提取接口

为避免重复加载，模型采用单例模式（首次调用时加载，之后复用）。
torch / transformers 未安装或模型下载失败时降级为零向量，系统仍可运行。
"""

import threading
from typing import Optional

from PIL import Image

from app.config import settings

# 单例锁
_MODEL_LOCK = threading.Lock()

# 全局模型实例
_clip_processor = None
_clip_model = None
_bge_tokenizer = None
_bge_model = None
_torch = None          # torch 模块（懒加载）
_np = None             # numpy 模块（懒加载）
_loaded = False
_load_attempted = False


def _import_torch():
    """懒加载 torch，返回模块或 None"""
    global _torch
    if _torch is not None:
        return _torch
    try:
        import torch
        _torch = torch
        return torch
    except ImportError:
        return None


def _import_numpy():
    """懒加载 numpy"""
    global _np
    if _np is not None:
        return _np
    try:
        import numpy
        _np = numpy
        return numpy
    except ImportError:
        return None


def _load_models():
    """加载 CLIP 和 BGE 模型（懒加载，线程安全）"""
    global _clip_processor, _clip_model, _bge_tokenizer, _bge_model, _loaded, _load_attempted
    if _loaded or _load_attempted:
        return
    with _MODEL_LOCK:
        if _loaded or _load_attempted:
            return
        _load_attempted = True
        torch = _import_torch()
        if torch is None:
            print("[警告] torch 未安装，向量模型不可用（降级零向量）。如需多模态检索请安装 torch + transformers")
            _loaded = True
            return

        device = settings.MODEL_DEVICE
        try:
            # ---------- 加载中文 CLIP ----------
            from transformers import ChineseCLIPProcessor, ChineseCLIPModel
            _clip_processor = ChineseCLIPProcessor.from_pretrained(settings.CLIP_MODEL_NAME)
            _clip_model = ChineseCLIPModel.from_pretrained(settings.CLIP_MODEL_NAME)
            _clip_model.to(device)
            _clip_model.eval()
            print("[模型] CLIP 加载成功")
        except Exception as e:
            print(f"[警告] CLIP 模型加载失败，将使用降级模式（零向量）：{e}")
            _clip_processor = None
            _clip_model = None

        try:
            # ---------- 加载 BGE 文本向量模型 ----------
            from transformers import AutoTokenizer, AutoModel
            _bge_tokenizer = AutoTokenizer.from_pretrained(settings.BGE_MODEL_NAME)
            _bge_model = AutoModel.from_pretrained(settings.BGE_MODEL_NAME)
            _bge_model.to(device)
            _bge_model.eval()
            print("[模型] BGE 加载成功")
        except Exception as e:
            print(f"[警告] BGE 模型加载失败，将使用降级模式（零向量）：{e}")
            _bge_tokenizer = None
            _bge_model = None

        _loaded = True


# BGE 文本向量化：使用 mean pooling + L2 归一化
def _bge_pooling(model_output, attention_mask):
    """Mean Pooling - 取 token 向量的注意力掩码均值"""
    torch = _torch
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
    sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    return sum_embeddings / sum_mask


def _l2_normalize(vec) -> list:
    """L2 归一化"""
    np = _import_numpy()
    if np is None:
        return vec
    arr = np.array(vec)
    norm = np.linalg.norm(arr)
    if norm < 1e-9:
        return vec
    return (arr / norm).tolist()


def extract_image_vector(image: Image.Image) -> list[float]:
    """提取图像向量（CLIP 或轻量降级）

    优先使用 CLIP 模型提取深度语义向量；
    CLIP 不可用时降级为颜色直方图+结构哈希特征（image_features 模块），
    确保图片检索在无 torch 环境下仍可工作。

    Args:
        image: PIL 图像对象
    Returns:
        归一化后的图像向量（list[float]，维度由模型决定，默认 512）
    """
    _load_models()
    if _clip_model is None or _clip_processor is None:
        # 降级：轻量级图像特征（颜色+结构+纹理）
        from app.utils.image_features import extract_image_features
        vec = extract_image_features(image, target_dim=settings.MILVUS_DIM)
        return vec
    torch = _import_torch()
    device = settings.MODEL_DEVICE
    with torch.no_grad():
        inputs = _clip_processor(images=image, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        features = _clip_model.get_image_features(**inputs)
        vec = features.cpu().numpy()[0]
        return _l2_normalize(vec.tolist())


def extract_text_vector(text: str) -> list[float]:
    """提取文本向量（BGE）

    Args:
        text: 文本描述
    Returns:
        归一化后的文本向量
    模型未加载时返回零向量。
    """
    _load_models()
    if _bge_model is None or _bge_tokenizer is None:
        return [0.0] * settings.MILVUS_TEXT_DIM
    torch = _import_torch()
    np = _import_numpy()
    device = settings.MODEL_DEVICE
    with torch.no_grad():
        inputs = _bge_tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        outputs = _bge_model(**inputs)
        pooled = _bge_pooling(outputs, inputs["attention_mask"])
        vec = pooled.cpu().numpy()[0]
        target_dim = settings.MILVUS_TEXT_DIM
        if len(vec) >= target_dim:
            vec = vec[:target_dim]
        else:
            vec = np.pad(vec, (0, target_dim - len(vec)))
        return _l2_normalize(vec.tolist())


def get_image_dim() -> int:
    """获取图像向量维度"""
    return settings.MILVUS_DIM


def get_text_dim() -> int:
    """获取文本向量维度"""
    return settings.MILVUS_TEXT_DIM
