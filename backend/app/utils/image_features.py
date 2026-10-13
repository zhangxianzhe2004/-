"""轻量级图像特征提取（无需 torch/transformers）

当 CLIP 模型不可用时作为降级方案，基于以下特征组合：
1. 颜色直方图（RGB 3通道 x 16 bins = 48 维）→ 捕捉颜色分布
2. 颜色矩（每通道均值+标准差 = 6 维）→ 捕捉整体色调
3. 平均哈希 aHash（8x8 = 64 维）→ 捕捉图像结构轮廓
4. 边缘方向直方图（8 个方向 = 8 维）→ 捕捉纹理特征

总维度：48 + 6 + 64 + 8 = 126，补齐到 512 维
经 L2 归一化后存入向量库，兼容现有余弦相似度检索。
"""

import math
from PIL import Image, ImageFilter

try:
    import numpy as np
except ImportError:
    np = None


def extract_image_features(image: Image.Image, target_dim: int = 512) -> list:
    """提取轻量级图像特征向量（无需 CLIP/torch）

    Args:
        image: PIL 图像
        target_dim: 目标维度（与 CLIP 向量维度对齐）
    Returns:
        L2 归一化后的特征向量
    """
    if image is None:
        return [0.0] * target_dim

    # 统一预处理：缩放到 224x224，转 RGB
    img = image.convert("RGB").resize((224, 224), Image.LANCZOS)

    features = []

    # ---------- 1. 颜色直方图（48 维）----------
    hist_r = img.histogram()[0:256]
    hist_g = img.histogram()[256:512]
    hist_b = img.histogram()[512:768]
    # 每通道压缩到 16 bins
    bins = 16
    for hist in [hist_r, hist_g, hist_b]:
        step = 256 // bins
        compressed = []
        for i in range(bins):
            compressed.append(sum(hist[i * step:(i + 1) * step]))
        # 归一化
        total = sum(compressed) or 1
        compressed = [h / total for h in compressed]
        features.extend(compressed)

    # ---------- 2. 颜色矩（6 维）----------
    if np is not None:
        arr = np.array(img, dtype=np.float64)
        for ch in range(3):  # R, G, B
            channel = arr[:, :, ch]
            mean = float(channel.mean()) / 255.0
            std = float(channel.std()) / 255.0
            features.append(mean)
            features.append(std)
    else:
        # numpy 不可用时的简单降级
        for ch in range(3):
            features.extend([0.5, 0.1])

    # ---------- 3. 平均哈希 aHash（64 维）----------
    # 缩小到 8x8 灰度图，与均值比较
    small_gray = image.convert("L").resize((8, 8), Image.LANCZOS)
    pixels = list(small_gray.getdata())
    avg = sum(pixels) / len(pixels) if pixels else 0
    ahash_bits = [1.0 if p >= avg else 0.0 for p in pixels]
    features.extend(ahash_bits)

    # ---------- 4. 边缘方向直方图（8 维）----------
    # 用 Sobel 近似边缘方向
    gray = img.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    if np is not None:
        edge_arr = np.array(edges, dtype=np.float64)
        # 按角度分 8 个方向 bin
        h, w = edge_arr.shape
        # 简化：将边缘强度按位置分 8 个扇区统计
        center_y, center_x = h / 2, w / 2
        edge_bins = [0.0] * 8
        for y in range(0, h, 4):  # 采样步长4，加速
            for x in range(0, w, 4):
                val = edge_arr[y, x]
                if val > 30:  # 边缘阈值
                    angle = math.atan2(y - center_y, x - center_x)
                    bin_idx = int(((angle + math.pi) / (2 * math.pi)) * 8) % 8
                    edge_bins[bin_idx] += val
        total_edge = sum(edge_bins) or 1
        edge_bins = [e / total_edge for e in edge_bins]
        features.extend(edge_bins)
    else:
        features.extend([0.125] * 8)

    # ---------- 补齐到目标维度 ----------
    if len(features) < target_dim:
        features.extend([0.0] * (target_dim - len(features)))
    else:
        features = features[:target_dim]

    # ---------- L2 归一化 ----------
    norm = math.sqrt(sum(v * v for v in features))
    if norm > 1e-9:
        features = [v / norm for v in features]

    return features


def is_clip_available() -> bool:
    """检查 CLIP 模型是否可用（用于判断是否使用降级特征）"""
    try:
        import torch  # noqa
        from transformers import ChineseCLIPModel  # noqa
        return True
    except ImportError:
        return False
