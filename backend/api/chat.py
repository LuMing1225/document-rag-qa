"""
问答 API 路由

- POST /api/chat/query     RAG 问答（混合检索 + LLM 生成）
- GET  /api/chat/retrieve  仅检索不生成（调试用）
"""
import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import TOP_K
from backend.models import QueryRequest, QueryResponse
from backend.state import state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/api/chat/query", response_model=QueryResponse)
async def chat_query(req: QueryRequest):
    """完整 RAG 问答：混合检索父文档 → LLM 生成答案。"""
    t0 = time.time()
    if req.kb_id not in state.knowledge_bases:
        raise HTTPException(status_code=404, detail=f"知识库不存在: {req.kb_id}")

    store = state.get_store(req.kb_id)
    loop = asyncio.get_event_loop()

    # 检索（阻塞操作放线程池）
    parents = await loop.run_in_executor(
        None,
        lambda: state.retriever.retrieve(
            question=req.question,
            store=store,
            top_k=req.top_k or TOP_K,
        ),
    )

    # 流式生成
    if req.stream:
        def _stream():
            for delta in state.generator.generate_stream(req.question, parents):
                yield delta
        return StreamingResponse(_stream(), media_type="text/plain; charset=utf-8")

    # 非流式生成
    answer = await loop.run_in_executor(
        None,
        lambda: state.generator.generate(req.question, parents),
    )
    elapsed = round(time.time() - t0, 2)
    return QueryResponse(
        question=req.question,
        answer=answer,
        retrieved_parents=parents,
        response_time=elapsed,
        model_used=state.generator.model,
    )


@router.get("/api/chat/retrieve")
async def chat_retrieve(
    question: str = Query(..., description="查询问题"),
    kb_id: str = Query("default", description="知识库 id"),
    top_k: int = Query(TOP_K, description="返回父文档数量"),
    use_reranker: bool = Query(True, description="是否启用重排器（性能测试设为False）"),
):
    """仅检索不生成（调试用），返回父文档及三路评分。"""
    if kb_id not in state.knowledge_bases:
        raise HTTPException(status_code=404, detail=f"知识库不存在: {kb_id}")
    store = state.get_store(kb_id)
    parents = state.retriever.retrieve(
        question=question, store=store, top_k=top_k, use_reranker=use_reranker
    )
    return {
        "question": question,
        "kb_id": kb_id,
        "use_reranker": use_reranker,
        "parents": [p.model_dump() for p in parents],
    }
