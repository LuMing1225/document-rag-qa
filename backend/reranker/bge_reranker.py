"""
BGE-Reranker-Large 重排器

- 加载本地 cross-encoder 模型：RERANKER_PATH
- 使用 transformers 的 AutoTokenizer + AutoModelForSequenceClassification
- 设备强制 CPU（把 8GB 显存留给 Ollama 上的 LLM）
- 输入 (query, document) 对，输出 logits 经 sigmoid 映射到 0~1 相关性分数
- 懒加载：首次调用 rerank() 时才真正加载模型，避免启动慢 / 无显存时阻塞
"""
import logging
from typing import List, Tuple

import torch

from backend.config import RERANKER_DEVICE, RERANKER_MAX_LEN, RERANKER_PATH

logger = logging.getLogger(__name__)


class BGEReranker:
    """BGE-Reranker-Large 重排器（CPU，懒加载）。"""

    def __init__(self) -> None:
        self.path = RERANKER_PATH
        self.device = RERANKER_DEVICE
        self._tokenizer = None
        self._model = None
        self._loaded = False

    # ------------------------------------------------------------------ #
    # 懒加载
    # ------------------------------------------------------------------ #
    def _ensure_loaded(self) -> None:
        """首次调用时加载 tokenizer 与模型（CPU）。"""
        if self._loaded:
            return
        logger.info("正在加载本地重排模型: %s (device=%s)", self.path, self.device)
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(self.path)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.path)
        self._model.eval()
        self._model.to(self.device)
        self._loaded = True
        logger.info("重排模型加载完成")

    # ------------------------------------------------------------------ #
    # 公共接口
    # ------------------------------------------------------------------ #
    def rerank(self, query: str, documents: List[str]) -> List[float]:
        """
        对一组 (query, document) 打分，返回 0~1 相关性列表，顺序与 documents 一致。

        参数:
            query: 查询文本
            documents: 候选文档文本列表（父文档）
        返回:
            与 documents 等长的分数列表（sigmoid(logit)）
        """
        if not documents:
            return []
        self._ensure_loaded()

        pairs = [[query, doc] for doc in documents]
        with torch.no_grad():
            inputs = self._tokenizer(
                pairs,
                padding=True,
                truncation=True,
                max_length=RERANKER_MAX_LEN,
                return_tensors="pt",
            ).to(self.device)
            outputs = self._model(**inputs)
            logits = outputs.logits.view(-1).float()
            # bge-reranker-large 单值输出 → sigmoid 映射到 0~1
            scores = torch.sigmoid(logits).cpu().numpy().tolist()

        logger.debug("重排 %d 个文档, query=%s", len(documents), query[:30])
        return [float(s) for s in scores]

    def rerank_pairs(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """
        直接对 (query, document) 对列表打分（同一 query 多次时由调用方自行组织）。
        """
        if not pairs:
            return []
        return self.rerank(pairs[0][0], [d for _, d in pairs])
