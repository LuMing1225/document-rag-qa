"""
知识库 API 路由

- POST /api/knowledge/create            创建知识库
- GET  /api/knowledge/list              知识库列表
- POST /api/knowledge/{kb_id}/index     对已解析文档构建父子分块 + 向量索引
- GET  /api/knowledge/{kb_id}/chunks    查看父子分块结构（分页，按父块）
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.config import VECTORSTORE_DIR
from backend.models import KnowledgeBase, ParseStatus
from backend.state import state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# ------------------------------------------------------------------ #
# 请求模型
# ------------------------------------------------------------------ #
class CreateKBRequest(BaseModel):
    name: str
    description: str = ""


class IndexRequest(BaseModel):
    doc_id: Optional[str] = None  # 为空时索引所有已解析文档


# ------------------------------------------------------------------ #
# 工具：保存知识库元信息
# ------------------------------------------------------------------ #
def _save_kb_meta(kb_id: str) -> None:
    """把知识库注册信息写到 kb_meta.json，供重启恢复。"""
    kb = state.knowledge_bases.get(kb_id)
    if not kb:
        return
    store = state.get_store(kb_id)
    doc_ids = [d for d, k in state.doc_to_kb.items() if k == kb_id]
    meta = {
        "kb_id": kb.kb_id,
        "name": kb.name,
        "description": kb.description,
        "document_count": len(doc_ids),
        "parent_count": store.count_parents(),
        "child_count": store.count_children(),
        "created_at": kb.created_at,
        "doc_ids": doc_ids,
    }
    kb_dir = Path(VECTORSTORE_DIR) / kb_id
    kb_dir.mkdir(parents=True, exist_ok=True)
    with open(kb_dir / "kb_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    # 同步更新内存对象，保证列表 API 立即反映最新计数
    kb.document_count = meta["document_count"]
    kb.parent_count = meta["parent_count"]
    kb.child_count = meta["child_count"]


# ------------------------------------------------------------------ #
# 路由
# ------------------------------------------------------------------ #
@router.post("/create")
async def create_kb(req: CreateKBRequest):
    """创建一个空知识库。"""
    kb_id = f"kb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    kb = KnowledgeBase(
        kb_id=kb_id,
        name=req.name,
        description=req.description,
        created_at=datetime.now().isoformat(),
    )
    state.knowledge_bases[kb_id] = kb
    state.get_store(kb_id)   # 初始化空索引目录
    _save_kb_meta(kb_id)
    logger.info("创建知识库: %s (%s)", req.name, kb_id)
    return kb.model_dump()


@router.get("/list")
async def list_kb():
    """知识库列表（含父子块数量统计）。"""
    result = []
    for kb_id, kb in state.knowledge_bases.items():
        store = state.get_store(kb_id)
        kb.parent_count = store.count_parents()
        kb.child_count = store.count_children()
        kb.document_count = sum(1 for d, k in state.doc_to_kb.items() if k == kb_id)
        result.append(kb.model_dump())
    return result


@router.post("/{kb_id}/index")
async def build_index(kb_id: str, req: IndexRequest):
    """
    对已解析文档构建父子分块 + 子文档向量索引。
    doc_id 为空时索引所有已解析文档（批量建库）。
    """
    if kb_id not in state.knowledge_bases:
        raise HTTPException(status_code=404, detail=f"知识库不存在: {kb_id}")

    # 确定要索引的文档列表
    if req.doc_id:
        doc_ids = [req.doc_id]
    else:
        doc_ids = [did for did, r in state.parse_results.items()
                   if r.status == ParseStatus.completed and r.chunks]
    if not doc_ids:
        raise HTTPException(status_code=400, detail="没有可索引的已解析文档，请先上传并解析 PDF")

    store = state.get_store(kb_id)
    total_parents = 0
    total_children = 0
    indexed_docs = []

    for doc_id in doc_ids:
        result = state.parse_results.get(doc_id)
        if result is None or result.status != ParseStatus.completed or not result.chunks:
            continue
        # 1. 父子分块
        parents, children = state.chunker.chunk(result.chunks, doc_id=doc_id)
        if not children:
            continue
        # 2. 子文档向量化
        child_texts = [c.text for c in children]
        logger.info("向量化 %d 个子文档 (doc=%s)", len(child_texts), doc_id)
        embeddings = state.embedder.embed(child_texts)
        if len(embeddings) != len(children):
            logger.warning("文档 %s 向量化数量不一致，跳过", doc_id)
            continue
        # 3. 写入向量库并持久化
        store.add(parents, children, embeddings)
        store.save()
        state.doc_to_kb[doc_id] = kb_id
        total_parents += len(parents)
        total_children += len(children)
        indexed_docs.append(doc_id)
        logger.info("文档 %s 已索引: 父=%d, 子=%d", doc_id, len(parents), len(children))

    _save_kb_meta(kb_id)

    if not indexed_docs:
        raise HTTPException(status_code=400, detail="所有文档索引失败，请检查 embedding 服务")

    return {
        "kb_id": kb_id,
        "indexed_docs": indexed_docs,
        "doc_count": len(indexed_docs),
        "parent_count": total_parents,
        "child_count": total_children,
        "total_parents": store.count_parents(),
        "total_children": store.count_children(),
    }


@router.get("/parsed_docs")
async def list_parsed_docs():
    """列出所有已解析文档（供前端选择索引）。"""
    docs = []
    for doc_id, r in state.parse_results.items():
        docs.append({
            "doc_id": doc_id,
            "filename": r.filename,
            "total_pages": r.total_pages,
            "chunk_count": len(r.chunks),
            "table_count": len(r.tables),
            "status": r.status.value,
            "kb_id": state.doc_to_kb.get(doc_id),
        })
    return docs


@router.get("/{kb_id}/chunks")
async def list_chunks(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页查看知识库中的父块（父子分块结构）。"""
    if kb_id not in state.knowledge_bases:
        raise HTTPException(status_code=404, detail=f"知识库不存在: {kb_id}")
    store = state.get_store(kb_id)
    return store.list_parents(page=page, page_size=page_size)
