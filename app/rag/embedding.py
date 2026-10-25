"""轻量本地 Embedding（字符 n-gram 哈希 + L2 归一化）。

为什么不用 ONNX / HuggingFace 模型：
- 部署环境下载 79MB 模型极慢（实测 ~15KB/s，要几小时），不可行；
- 本方案零依赖、完全离线，Windows/Linux 都能跑；
- 对同领域中文文本（游戏世界观/关卡设定）的检索够用。

工程权衡（面试可讲）：
- 保留了完整的「向量化 → 存储 → 余弦相似度检索」RAG 流程；
- 只把 embedding 换成轻量实现，接口兼容 Chroma 的 EmbeddingFunction；
- 后续可无缝切换到 BGE / OpenAI embedding，不用改业务代码。
"""
import hashlib
import math
from typing import Any, Dict

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings


class SimpleHashEmbedding(EmbeddingFunction[Documents]):
    """字符 n-gram 哈希 embedding。"""

    def __init__(self, dim: int = 512):
        self._dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        text = (text or "").lower()
        # 中文友好：用 2-gram / 3-gram 字符片段
        for n in (2, 3):
            for i in range(len(text) - n + 1):
                gram = text[i:i + n]
                digest = hashlib.md5(gram.encode("utf-8")).digest()
                h = int.from_bytes(digest[:8], "big")
                idx = h % self._dim
                sign = 1.0 if (h >> 12) & 1 else -1.0
                vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def name() -> str:
        return "simple_hash"

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "SimpleHashEmbedding":
        return SimpleHashEmbedding(dim=config.get("dim", 512))

    def get_config(self) -> Dict[str, Any]:
        return {"dim": self._dim}
