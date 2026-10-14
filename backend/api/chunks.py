"""
父子分块查看 API 路由

- GET /api/chunks/{kb_id}              分页查看父块及其子块结构
- GET /api/chunks/{kb_id}/parents      分页查看父块
- GET /api/chunks/{kb_id}/children     查看某父块下的全部子块
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.state import state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chunks", tags=["chunks"])


@router.get("/{kb_id}")
async def view_chunks(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """
    分页查看父块，并附带每个父块下的子块 id 列表与子块数量。
    用于前端可视化父子分块结构。
    """
    if kb_id not in state.knowledge_bases:
        raise HTTPException(status_code=404, detail=f"知识库不存在: {kb_id}")
    store = state.get_store(kb_id)
    page_data = store.list_parents(page=page, page_size=page_size)

    items = []
    for p in page_data["items"]:
        items.append({
            "parent_id": p["parent_id"],
            "heading_path": p.get("heading_path", ""),
            "layout_type": p.get("layout_type", "text"),
            "page_numbers": p.get("page_numbers", []),
            "child_count": len(p.get("child_ids", [])),
            "child_ids": p.get("child_ids", []),
            "text_preview": p["text"][:120] + ("……" if len(p["text"]) > 120 else ""),
            "text_length": len(p["text"]),
        })
    return {
        "kb_id": kb_id,
        "total_parents": page_data["total"],
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get("/{kb_id}/parents")
async def view_parents(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页查看父块完整内容。"""
    if kb_id not in state.knowledge_bases:
        raise HTTPException(status_code=404, detail=f"知识库不存在: {kb_id}")
    store = state.get_store(kb_id)
    return store.list_parents(page=page, page_size=page_size)


@router.get("/{kb_id}/children/{parent_id}")
async def view_children(kb_id: str, parent_id: str):
    """查看某个父块下的全部子块（通过 child_meta 反查）。"""
    if kb_id not in state.knowledge_bases:
        raise HTTPException(status_code=404, detail=f"知识库不存在: {kb_id}")
    store = state.get_store(kb_id)
    parent = store.get_parent(parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail=f"父块不存在: {parent_id}")

    # 从 child_meta 中筛出属于该父块的子块
    children = [c for c in store.child_meta if c.get("parent_id") == parent_id]
    return {
        "parent_id": parent_id,
        "parent_text": parent["text"],
        "heading_path": parent.get("heading_path", ""),
        "page_numbers": parent.get("page_numbers", []),
        "child_count": len(children),
        "children": children,
    }
