"""
FAISS 向量库（父子双索引设计）

- child_index: 子文档向量索引（IndexFlatIP，L2 归一化后内积即余弦相似度）
- child_meta: 与索引行一一对应的子文档元数据（含 parent_id）
- parent_store: 父文档元数据字典（parent_id -> 完整父文档），父文档不单独建向量，
  而是通过 child -> parent 映射间接被检索到

持久化（Windows 中文路径必须用 serialize_index/deserialize_index，不能用 write_index）：
    data/vectorstore/{kb_id}/
        ├── child.index       # serialize_index 得到的 bytes
        ├── child_meta.json   # 子文档元数据列表
        ├── parent_store.json # 父文档字典
        └── kb_meta.json     # 知识库注册信息
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import numpy as np

from backend.config import EMBEDDING_DIM, VECTORSTORE_DIR
from backend.models import ChildChunk, ParentChunk

logger = logging.getLogger(__name__)


class FAISSStore:
    """父子双索引 FAISS 向量库封装。"""

    def __init__(self, kb_id: str, dimension: int = EMBEDDING_DIM) -> None:
        self.kb_id = kb_id
        self.dimension = dimension
        self.kb_dir = Path(VECTORSTORE_DIR) / kb_id
        self.kb_dir.mkdir(parents=True, exist_ok=True)

        # 文件路径
        self.child_index_path = self.kb_dir / "child.index"
        self.child_meta_path = self.kb_dir / "child_meta.json"
        self.parent_store_path = self.kb_dir / "parent_store.json"

        # 内存对象
        self.child_index: Optional[faiss.IndexFlatIP] = None
        self.child_meta: List[Dict[str, Any]] = []
        self.parent_store: Dict[str, Dict[str, Any]] = {}

        self.load()

    # ------------------------------------------------------------------ #
    # 写入
    # ------------------------------------------------------------------ #
    def add(
        self,
        parents: List[ParentChunk],
        children: List[ChildChunk],
        child_embeddings: List[List[float]],
    ) -> None:
        """
        把一批父子块及其子文档向量写入索引。

        参数:
            parents: 父块列表
            children: 子块列表（与 child_embeddings 等长且对齐）
            child_embeddings: 与 children 等长的 1024 维向量
        """
        if not children or not child_embeddings:
            logger.warning("add 收到空的 children/embeddings，跳过")
            return

        if self.child_index is None:
            self.child_index = faiss.IndexFlatIP(self.dimension)

        # 1. 登记父文档
        for p in parents:
            self.parent_store[p.parent_id] = {
                "parent_id": p.parent_id,
                "text": p.text,
                "page_numbers": p.page_numbers,
                "child_ids": p.child_ids,
                "heading_path": p.heading_path,
                "layout_type": p.layout_type,
                "metadata": p.metadata,
            }

        # 2. 子文档向量入索引（L2 归一化，内积即余弦）
        vecs = np.array(child_embeddings, dtype=np.float32)
        faiss.normalize_L2(vecs)
        self.child_index.add(vecs)

        # 3. 子文档元数据对齐索引行
        for c in children:
            self.child_meta.append({
                "child_id": c.child_id,
                "parent_id": c.parent_id,
                "text": c.text,
                "page_number": c.page_number,
                "position_tag": c.position_tag,
                "layout_type": c.layout_type,
                "heading_path": c.heading_path,
            })

        logger.info(
            "FAISS 写入: +%d 子向量, +%d 父文档; 索引总子数=%d, 父数=%d",
            len(children), len(parents),
            self.child_index.ntotal, len(self.parent_store),
        )

    # ------------------------------------------------------------------ #
    # 检索
    # ------------------------------------------------------------------ #
    def search_children(
        self,
        query_embedding: List[float],
        recall_k: int = 15,
        threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        第一阶段：在子文档索引上做稠密检索，返回候选子文档。

        返回每个元素:
            {child_id, parent_id, text, page_number, layout_type, heading_path, dense_score}
        """
        if self.child_index is None or self.child_index.ntotal == 0:
            return []

        q = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(q)
        k = min(recall_k, self.child_index.ntotal)
        scores, indices = self.child_index.search(q, k)

        results: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            if score < threshold:
                continue
            m = self.child_meta[idx]
            results.append({
                "child_id": m["child_id"],
                "parent_id": m["parent_id"],
                "text": m["text"],
                "page_number": m["page_number"],
                "layout_type": m["layout_type"],
                "heading_path": m["heading_path"],
                "dense_score": float(score),
            })
        return results

    def get_parent(self, parent_id: str) -> Optional[Dict[str, Any]]:
        """按 parent_id 取父文档完整信息。"""
        return self.parent_store.get(parent_id)

    def all_parents(self) -> List[Dict[str, Any]]:
        """返回所有父文档（用于分块查看 API）。"""
        return list(self.parent_store.values())

    # ------------------------------------------------------------------ #
    # 持久化
    # ------------------------------------------------------------------ #
    def save(self) -> None:
        """
        持久化到磁盘。
        注意：FAISS 在 Windows 中文路径下不能用 write_index，
        必须用 serialize_index 得到 bytes 再用 Python open() 写文件。
        """
        # 子向量索引
        if self.child_index is not None:
            index_bytes = faiss.serialize_index(self.child_index)
            with open(self.child_index_path, "wb") as f:
                f.write(index_bytes.tobytes())

        # 元数据 JSON
        with open(self.child_meta_path, "w", encoding="utf-8") as f:
            json.dump(self.child_meta, f, ensure_ascii=False, indent=2)
        with open(self.parent_store_path, "w", encoding="utf-8") as f:
            json.dump(self.parent_store, f, ensure_ascii=False, indent=2)

        logger.info("FAISS 索引已保存: %s (子=%d, 父=%d)",
                    self.kb_dir, self.count_children(), self.count_parents())

    def load(self) -> None:
        """从磁盘加载；不存在则初始化空索引。"""
        if self.child_index_path.exists() and self.child_meta_path.exists():
            try:
                with open(self.child_index_path, "rb") as f:
                    raw = f.read()
                index_arr = np.frombuffer(raw, dtype=np.uint8)
                self.child_index = faiss.deserialize_index(index_arr)

                with open(self.child_meta_path, "r", encoding="utf-8") as f:
                    self.child_meta = json.load(f)
                if self.parent_store_path.exists():
                    with open(self.parent_store_path, "r", encoding="utf-8") as f:
                        self.parent_store = json.load(f)
                logger.info("加载已有 FAISS 索引: %s, 子=%d, 父=%d",
                            self.kb_id,
                            self.child_index.ntotal, len(self.parent_store))
                return
            except Exception as e:
                logger.warning("加载 FAISS 索引失败，重建空索引: %s", e)

        self.child_index = faiss.IndexFlatIP(self.dimension)
        self.child_meta = []
        self.parent_store = {}

    # ------------------------------------------------------------------ #
    # 统计 / 分页
    # ------------------------------------------------------------------ #
    def count_children(self) -> int:
        return self.child_index.ntotal if self.child_index is not None else 0

    def count_parents(self) -> int:
        return len(self.parent_store)

    def list_parents(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """分页列出父文档（父子分块查看 API）。"""
        parents = self.all_parents()
        total = len(parents)
        start = (page - 1) * page_size
        end = start + page_size
        items = parents[start:end]
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }
