"""
Milvus 向量库（父子双存储设计）

- 子文档向量存入 Milvus Collection（rag_{kb_id}），用于稠密向量检索
- 父文档存在本地 JSON（parent_store.json），只需按 ID 取原文，不需要向量检索

持久化：
    data/vectorstore/{kb_id}/
        ├── parent_store.json  # 父文档字典（本地持久化）
        └── kb_meta.json       # 知识库注册信息
    Milvus 侧：
        Collection: rag_{kb_id}  # 子文档向量自动持久化到 Milvus 集群
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from backend.config import EMBEDDING_DIM, VECTORSTORE_DIR
from backend.models import ChildChunk, ParentChunk

logger = logging.getLogger(__name__)

# Milvus 连接参数
MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"


class MilvusStore:
    """父子双存储 Milvus 向量库封装，接口与 FAISSStore 完全兼容。"""

    def __init__(self, kb_id: str, dimension: int = EMBEDDING_DIM) -> None:
        self.kb_id = kb_id
        self.dimension = dimension
        self.kb_dir = Path(VECTORSTORE_DIR) / kb_id
        self.kb_dir.mkdir(parents=True, exist_ok=True)

        # 文件路径（父文档本地持久化）
        self.parent_store_path = self.kb_dir / "parent_store.json"

        # Milvus collection 名
        self.collection_name = f"rag_{kb_id}"

        # 内存中的父文档字典
        self.parent_store: Dict[str, Dict[str, Any]] = {}

        # Milvus 句柄
        self._collection = None
        self._connected = False

        # 尝试连接 Milvus
        self._connect_milvus()

        # 加载本地父文档
        self.load()

    # ------------------------------------------------------------------ #
    # Milvus 连接与 Collection 管理
    # ------------------------------------------------------------------ #
    def _connect_milvus(self) -> None:
        """连接 Milvus 并创建/加载 collection。连接失败时优雅降级。"""
        try:
            from pymilvus import (
                connections,
                utility,
                Collection,
                CollectionSchema,
                FieldSchema,
                DataType,
            )

            # 检查是否已连接
            try:
                connections.connect(
                    alias="default",
                    host=MILVUS_HOST,
                    port=MILVUS_PORT,
                )
            except Exception:
                # 可能已经连接过了，忽略
                pass

            # 检查 collection 是否存在
            if utility.has_collection(self.collection_name):
                self._collection = Collection(self.collection_name)
                self._collection.load()
                self._connected = True
                logger.info(
                    "Milvus collection 已加载: %s (实体数=%d)",
                    self.collection_name,
                    self._collection.num_entities,
                )
            else:
                # 创建新 collection
                self._create_collection()
                self._connected = True
                logger.info("Milvus collection 已创建: %s", self.collection_name)

        except Exception as e:
            logger.warning(
                "Milvus 连接失败，将以降级模式运行（向量检索不可用，仅父文档本地存储）: %s",
                e,
            )
            self._connected = False
            self._collection = None

    def _create_collection(self) -> None:
        """在 Milvus 中创建 collection schema 和索引。"""
        from pymilvus import (
            Collection,
            CollectionSchema,
            FieldSchema,
            DataType,
        )

        fields = [
            FieldSchema(name="child_id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
            FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="page_number", dtype=DataType.INT64),
            FieldSchema(name="layout_type", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="heading_path", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
        ]
        schema = CollectionSchema(fields=fields, description=f"RAG child chunks for {self.kb_id}")
        self._collection = Collection(name=self.collection_name, schema=schema)

        # 创建 IVF_FLAT 索引（内积 IP，向量需 L2 归一化）
        index_params = {
            "metric_type": "IP",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024},
        }
        self._collection.create_index(field_name="embedding", index_params=index_params)
        self._collection.load()

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
        把一批父子块及其子文档向量写入存储。

        参数:
            parents: 父块列表
            children: 子块列表（与 child_embeddings 等长且对齐）
            child_embeddings: 与 children 等长的 1024 维向量
        """
        if not children or not child_embeddings:
            logger.warning("add 收到空的 children/embeddings，跳过")
            return

        # 1. 登记父文档到本地字典
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

        # 2. 子文档向量写入 Milvus（L2 归一化，内积即余弦）
        if self._connected and self._collection is not None:
            try:
                vecs = np.array(child_embeddings, dtype=np.float32)
                # L2 归一化（与 FAISS 版保持一致）
                norms = np.linalg.norm(vecs, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                vecs_normalized = vecs / norms

                # 构建插入数据
                child_ids = [c.child_id for c in children]
                parent_ids = [c.parent_id for c in children]
                texts = [c.text for c in children]
                page_numbers = [c.page_number for c in children]
                layout_types = [c.layout_type for c in children]
                heading_paths = [c.heading_path for c in children]

                insert_data = [
                    child_ids,
                    parent_ids,
                    texts,
                    page_numbers,
                    layout_types,
                    heading_paths,
                    vecs_normalized.tolist(),
                ]

                self._collection.insert(insert_data)
                self._collection.flush()

                logger.info(
                    "Milvus 写入: +%d 子向量, +%d 父文档; 父数=%d",
                    len(children), len(parents), len(self.parent_store),
                )
                return
            except Exception as e:
                logger.error("Milvus 写入失败: %s", e)
                # 降级：至少保存父文档
                self.save()
        else:
            logger.warning(
                "Milvus 未连接，仅保存父文档到本地（子向量未入库）: +%d 父文档",
                len(parents),
            )
            self.save()

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
        第一阶段：在子文档向量索引上做稠密检索，返回候选子文档。

        返回每个元素:
            {child_id, parent_id, text, page_number, layout_type, heading_path, dense_score}
        """
        if not self._connected or self._collection is None:
            logger.warning("Milvus 未连接，无法检索子文档")
            return []

        try:
            # L2 归一化查询向量
            q = np.array([query_embedding], dtype=np.float32)
            norm = np.linalg.norm(q)
            if norm > 0:
                q = q / norm

            # Milvus 向量搜索
            search_params = {
                "metric_type": "IP",
                "params": {"nprobe": 16},
            }
            k = min(recall_k, self.count_children())
            if k <= 0:
                return []

            output_fields = [
                "child_id", "parent_id", "text",
                "page_number", "layout_type", "heading_path",
            ]
            results = self._collection.search(
                data=q.tolist(),
                anns_field="embedding",
                param=search_params,
                limit=k,
                output_fields=output_fields,
            )

            hits = results[0]
            output: List[Dict[str, Any]] = []
            for hit in hits:
                score = float(hit.score)
                if score < threshold:
                    continue
                entity = hit.entity
                # pymilvus 2.3.4 的 Entity.get() 不支持默认值参数，改用 getattr
                output.append({
                    "child_id": getattr(entity, "child_id", ""),
                    "parent_id": getattr(entity, "parent_id", ""),
                    "text": getattr(entity, "text", ""),
                    "page_number": getattr(entity, "page_number", 0),
                    "layout_type": getattr(entity, "layout_type", "text"),
                    "heading_path": getattr(entity, "heading_path", ""),
                    "dense_score": score,
                })
            return output

        except Exception as e:
            logger.error("Milvus 检索失败: %s", e)
            return []

    def get_parent(self, parent_id: str) -> Optional[Dict[str, Any]]:
        """按 parent_id 取父文档完整信息（从本地 JSON 字典）。"""
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
        Milvus 中的子向量自动持久化到集群，这里只需保存父文档 JSON。
        """
        with open(self.parent_store_path, "w", encoding="utf-8") as f:
            json.dump(self.parent_store, f, ensure_ascii=False, indent=2)

        logger.info(
            "父文档已保存: %s (父=%d)",
            self.parent_store_path,
            self.count_parents(),
        )

    def load(self) -> None:
        """从磁盘加载父文档 JSON；不存在则初始化为空字典。"""
        if self.parent_store_path.exists():
            try:
                with open(self.parent_store_path, "r", encoding="utf-8") as f:
                    self.parent_store = json.load(f)
                logger.info(
                    "加载父文档存储: %s, 父=%d",
                    self.kb_id,
                    len(self.parent_store),
                )
                return
            except Exception as e:
                logger.warning("加载父文档存储失败，重新初始化: %s", e)

        self.parent_store = {}

    # ------------------------------------------------------------------ #
    # 统计 / 分页
    # ------------------------------------------------------------------ #
    def count_children(self) -> int:
        """返回 Milvus collection 中的子文档实体数。"""
        if not self._connected or self._collection is None:
            return 0
        try:
            return self._collection.num_entities
        except Exception:
            return 0

    def count_parents(self) -> int:
        """返回本地父文档字典中的父文档数。"""
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
