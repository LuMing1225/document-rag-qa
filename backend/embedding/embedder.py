# -*- coding: utf-8 -*-
"""
嵌入向量器（Embedder）

通过 Ollama /api/embeddings 调用 bge-m3:latest 生成 1024 维向量。
GPU 显存由 Ollama 自行管理，本服务只发 HTTP 请求。
"""
import logging
from typing import List

import requests

from backend.config import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_TIMEOUT,
)

logger = logging.getLogger(__name__)

# bge-m3 支持 8192 token，但子块本身很小（≤450 字），这里留宽一点即可
MAX_CHARS = 1024


class Embedder:
    """文本向量化器（基于 Ollama /api/embeddings）。"""

    def __init__(self) -> None:
        self.api_url = f"{OLLAMA_BASE_URL}/api/embeddings"
        self.model = EMBEDDING_MODEL
        self.dim = EMBEDDING_DIM

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成嵌入向量。逐条调用 /api/embeddings（该端点稳定可用）。

        参数:
            texts: 文本列表
        返回:
            与 texts 等长的 1024 维向量列表
        """
        if not texts:
            return []
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        """单条查询向量化。POST /api/embeddings，响应 {"embedding": [...]}。"""
        if not text:
            return [0.0] * self.dim
        text = text[:MAX_CHARS]
        try:
            payload = {"model": self.model, "prompt": text}
            resp = requests.post(self.api_url, json=payload, timeout=OLLAMA_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            emb = data.get("embedding")
            if emb and len(emb) > 0:
                return emb
            # 兼容 /api/embed 格式
            embs = data.get("embeddings")
            if embs and len(embs) > 0:
                return embs[0]
            logger.warning("嵌入返回为空，使用零向量: %s", str(data)[:200])
            return [0.0] * self.dim
        except Exception as e:
            logger.exception("嵌入失败，使用零向量: %s", e)
            return [0.0] * self.dim
