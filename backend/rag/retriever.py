"""
混合检索器（Retriever）

两阶段检索 + 多向量评分：
1. 第一阶段：子文档稠密向量检索（bge-m3），召回 RECALL_K 个候选子文档
2. 父文档去重：同一 parent_id 的多个子文档只保留 dense_score 最高的那个
3. 第二阶段：BGE-Reranker-Large 对去重后的父文档做精排（CPU cross-encoder）
4. 多向量评分公式：
        Score_final = β · Sim_Dense(Query, Child) + (1-β) · Sim_Rerank(Query, Parent)
   其中 β = BETA（默认 0.4）
5. 按 Score_final 降序取 top_k 个父文档作为最终上下文
"""
import logging
from typing import Dict, List, Optional

from backend.config import BETA, RECALL_K, SIMILARITY_THRESHOLD, TOP_K
from backend.embedding.embedder import Embedder
from backend.glossary import expand_query
from backend.models import RetrievedParent
from backend.reranker.bge_reranker import BGEReranker
from backend.vectorstore.milvus_store import MilvusStore

logger = logging.getLogger(__name__)


class Retriever:
    """RAG 混合检索器。"""

    def __init__(self, embedder: Embedder, reranker: BGEReranker) -> None:
        self.embedder = embedder
        self.reranker = reranker

    def retrieve(
        self,
        question: str,
        store: MilvusStore,
        top_k: int = TOP_K,
        use_reranker: bool = True,
    ) -> List[RetrievedParent]:
        """
        完整检索流程，返回 top_k 个父文档（含三路评分）。
        use_reranker=False 时跳过重排器（仅稠密检索，用于性能压测）。
        """
        # 0. 母婴领域词汇表查询扩展（同义词/相关术语扩展）
        expanded_question = expand_query(question)
        if expanded_question != question:
            logger.info("查询扩展: '%s' -> '%s'", question[:40], expanded_question[:80])

        # 1. 查询向量化（使用扩展后的查询）
        q_emb = self.embedder.embed_query(expanded_question)

        # 2. 子文档稠密召回
        children = store.search_children(
            q_emb, recall_k=RECALL_K, threshold=SIMILARITY_THRESHOLD
        )
        if not children:
            # 阈值过严时放宽再试一次
            children = store.search_children(q_emb, recall_k=RECALL_K, threshold=0.1)
        if not children:
            logger.info("检索无候选子文档: %s", question[:40])
            return []

        # 3. 父文档去重：同一 parent 只保留 dense 分最高的子文档
        best_child_by_parent: Dict[str, Dict] = {}
        for ch in children:
            pid = ch["parent_id"]
            if pid not in best_child_by_parent or ch["dense_score"] > best_child_by_parent[pid]["dense_score"]:
                best_child_by_parent[pid] = ch

        # 4. 取出对应父文档完整内容
        parent_ids = list(best_child_by_parent.keys())
        parent_texts: List[str] = []
        parent_infos: List[Dict] = []
        for pid in parent_ids:
            pinfo = store.get_parent(pid)
            if pinfo is None:
                continue
            parent_texts.append(pinfo["text"])
            parent_infos.append(pinfo)

        if not parent_texts:
            return []

        # 5. BGE-Reranker 精排父文档（使用扩展后的查询），可跳过；失败时自动降级为仅稠密
        if use_reranker:
            try:
                rerank_scores = self.reranker.rerank(expanded_question, parent_texts)
            except Exception as e:
                logger.warning("重排器调用失败，自动降级为仅稠密检索: %s", e)
                use_reranker = False
                rerank_scores = [0.0] * len(parent_texts)
        else:
            rerank_scores = [0.0] * len(parent_texts)

        # 6. 多向量评分融合（跳过重排时 β=1.0，仅用 dense 分）
        beta = BETA if use_reranker else 1.0
        results: List[RetrievedParent] = []
        for pinfo, dense_ch, rscore in zip(parent_infos,
                                           [best_child_by_parent[p["parent_id"]] for p in parent_infos],
                                           rerank_scores):
            dense_score = float(dense_ch["dense_score"])
            rscore = float(rscore)
            final = beta * dense_score + (1 - beta) * rscore
            results.append(RetrievedParent(
                parent_id=pinfo["parent_id"],
                text=pinfo["text"],
                score=round(final, 6),
                dense_score=round(dense_score, 6),
                rerank_score=round(rscore, 6),
                page_numbers=pinfo.get("page_numbers", []),
                child_count=len(pinfo.get("child_ids", [])),
                heading_path=pinfo.get("heading_path", ""),
                layout_type=pinfo.get("layout_type", "text"),
            ))

        # 7. 按最终分降序，取 top_k
        results.sort(key=lambda r: -r.score)
        final = results[:top_k]
        logger.info(
            "检索完成: 召回子=%d -> 去重父=%d -> 最终父=%d (β=%.1f, reranker=%s)",
            len(children), len(parent_infos), len(final), beta, use_reranker,
        )
        return final
