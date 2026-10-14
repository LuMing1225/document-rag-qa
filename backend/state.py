"""
全局状态（AppState 单例）

集中持有：
- 解析器、分块器、嵌入器、重排器、检索器、生成器 等组件
- 内存中的解析结果、解析状态、知识库注册表、Milvus 句柄、doc->kb 映射
- 启动时从 data/parsed 与 data/vectorstore 恢复已持久化的数据
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from backend.config import PARSED_DIR, VECTORSTORE_DIR
from backend.models import (
    KnowledgeBase,
    LayoutRegion,
    ParseResult,
    TextChunk,
)
from backend.parser.pdf_parser import PDFParser
from backend.chunker.parent_child_chunker import ParentChildChunker
from backend.embedding.embedder import Embedder
from backend.reranker.bge_reranker import BGEReranker
from backend.rag.retriever import Retriever
from backend.rag.generator import Generator

logger = logging.getLogger(__name__)


class AppState:
    """全局应用状态（单例）。"""

    def __init__(self) -> None:
        # 核心组件
        self.parser = PDFParser()
        self.chunker = ParentChildChunker()
        self.embedder = Embedder()
        self.reranker = BGEReranker()
        self.retriever = Retriever(self.embedder, self.reranker)
        self.generator = Generator()

        # 内存状态
        self.parse_status: Dict[str, Dict] = {}
        self.parse_results: Dict[str, ParseResult] = {}
        self.knowledge_bases: Dict[str, KnowledgeBase] = {}
        self.stores: Dict[str, object] = {}       # kb_id -> MilvusStore
        self.doc_to_kb: Dict[str, str] = {}     # doc_id -> kb_id

        # 启动时从磁盘恢复
        self._load_parsed_from_disk()
        self._load_kbs_from_disk()

    # ------------------------------------------------------------------ #
    # 磁盘恢复
    # ------------------------------------------------------------------ #
    def _load_parsed_from_disk(self) -> None:
        """从 data/parsed/*.json 恢复已解析文档。"""
        try:
            PARSED_DIR.mkdir(parents=True, exist_ok=True)
            count = 0
            for f in PARSED_DIR.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                    chunks = [TextChunk(**c) for c in data.get("chunks", [])]
                    regions = [LayoutRegion(**r) for r in data.get("layout_regions", [])]
                    result = ParseResult(
                        doc_id=data["doc_id"],
                        filename=data.get("filename", f.stem),
                        total_pages=data.get("total_pages", 0),
                        status=data.get("status", "completed"),
                        chunks=chunks,
                        layout_regions=regions,
                        tables=data.get("tables", []),
                        full_text=data.get("full_text", ""),
                        parse_time=data.get("parse_time", 0.0),
                        error=data.get("error", ""),
                    )
                    self.parse_results[result.doc_id] = result
                    self.parse_status[result.doc_id] = {
                        "status": result.status,
                        "progress": 100,
                        "message": f"已恢复（磁盘），{len(chunks)} 块",
                        "filename": result.filename,
                    }
                    count += 1
                except Exception as e:
                    logger.warning("恢复解析结果失败 %s: %s", f.name, e)
            if count:
                logger.info("从磁盘恢复 %d 个已解析文档", count)
        except Exception as e:
            logger.warning("加载磁盘解析结果失败: %s", e)

    def _load_kbs_from_disk(self) -> None:
        """从 data/vectorstore/*/kb_meta.json 恢复知识库注册信息。"""
        try:
            VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
            count = 0
            for kb_dir in VECTORSTORE_DIR.iterdir():
                if not kb_dir.is_dir():
                    continue
                meta_path = kb_dir / "kb_meta.json"
                if not meta_path.exists():
                    continue
                try:
                    with open(meta_path, "r", encoding="utf-8") as fp:
                        meta = json.load(fp)
                    kb = KnowledgeBase(
                        kb_id=meta.get("kb_id", kb_dir.name),
                        name=meta.get("name", kb_dir.name),
                        description=meta.get("description", ""),
                        document_count=meta.get("document_count", 0),
                        parent_count=meta.get("parent_count", 0),
                        child_count=meta.get("child_count", 0),
                        created_at=meta.get("created_at", ""),
                    )
                    self.knowledge_bases[kb.kb_id] = kb
                    for doc_id in meta.get("doc_ids", []):
                        self.doc_to_kb[doc_id] = kb.kb_id
                    count += 1
                except Exception as e:
                    logger.warning("恢复知识库失败 %s: %s", kb_dir.name, e)
            if count:
                logger.info("从磁盘恢复 %d 个知识库", count)
        except Exception as e:
            logger.warning("加载磁盘知识库失败: %s", e)

    # ------------------------------------------------------------------ #
    # 工具
    # ------------------------------------------------------------------ #
    def get_store(self, kb_id: str):
        """获取（或懒加载）某知识库的 MilvusStore。"""
        from backend.vectorstore.milvus_store import MilvusStore
        if kb_id not in self.stores:
            self.stores[kb_id] = MilvusStore(kb_id)
        return self.stores[kb_id]


# 全局单例
state = AppState()
