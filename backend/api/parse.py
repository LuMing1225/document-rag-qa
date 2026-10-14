"""
解析 API 路由

- POST /api/parse/upload   上传 PDF 并立即完成版面分析解析
- GET  /api/parse/{doc_id} 获取解析结果（含版面区域可视化数据）
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import PARSED_DIR, UPLOAD_DIR
from backend.models import ParseStatus
from backend.state import state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/parse", tags=["parse"])


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    上传 PDF 文件并同步完成版面分析解析。

    返回: doc_id、文件名、页数、状态，以及版面区域数量与表格数量摘要。
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    doc_id = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOAD_DIR / f"{doc_id}_{file.filename}"

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    logger.info("上传 PDF: %s -> %s (%d 字节)", file.filename, doc_id, len(content))

    # 在线程池中执行阻塞式 PDF 解析
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: state.parser.parse(pdf_path=str(save_path), doc_id=doc_id),
    )

    if result.status != ParseStatus.completed:
        raise HTTPException(status_code=500, detail=f"解析失败: {result.error}")

    # 持久化解析结果
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PARSED_DIR / f"{doc_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)

    state.parse_results[doc_id] = result
    state.parse_status[doc_id] = {
        "status": result.status.value,
        "progress": 100,
        "message": f"解析完成，{len(result.chunks)} 块",
        "filename": result.filename,
    }

    # 统计版面区域类型分布（用于前端可视化）
    region_types: dict = {}
    for r in result.layout_regions:
        region_types[r.type] = region_types.get(r.type, 0) + 1

    return {
        "doc_id": doc_id,
        "filename": result.filename,
        "total_pages": result.total_pages,
        "status": result.status.value,
        "chunk_count": len(result.chunks),
        "region_count": len(result.layout_regions),
        "table_count": len(result.tables),
        "region_types": region_types,
        "parse_time": result.parse_time,
        "layout_regions": [r.model_dump() for r in result.layout_regions],
    }


@router.get("/{doc_id}")
async def get_parse_result(doc_id: str):
    """获取某文档的完整解析结果（含版面区域、表格、全文）。"""
    result = state.parse_results.get(doc_id)
    if result is None:
        # 尝试从磁盘加载
        f = PARSED_DIR / f"{doc_id}.json"
        if f.exists():
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            from backend.models import LayoutRegion, TextChunk
            result = ParseResult(
                doc_id=data["doc_id"],
                filename=data.get("filename", ""),
                total_pages=data.get("total_pages", 0),
                status=data.get("status", "completed"),
                chunks=[TextChunk(**c) for c in data.get("chunks", [])],
                layout_regions=[LayoutRegion(**r) for r in data.get("layout_regions", [])],
                tables=data.get("tables", []),
                full_text=data.get("full_text", ""),
                parse_time=data.get("parse_time", 0.0),
                error=data.get("error", ""),
            )
            state.parse_results[doc_id] = result
        else:
            raise HTTPException(status_code=404, detail=f"解析结果不存在: {doc_id}")

    resp = {
        "doc_id": result.doc_id,
        "filename": result.filename,
        "total_pages": result.total_pages,
        "status": result.status.value,
        "chunks": [c.model_dump() for c in result.chunks],
        "layout_regions": [r.model_dump() for r in result.layout_regions],
        "tables": result.tables,
        "full_text": result.full_text,
        "parse_time": result.parse_time,
    }
    if result.error:
        resp["error"] = result.error
    return resp
