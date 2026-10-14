"""
FastAPI 入口：母婴护理垂直领域长文本版面分析 RAG 检索增强系统

启动方式（在项目根目录）：
    conda run -n pdfqa uvicorn backend.main:app --host 0.0.0.0 --port 8563
或直接运行 start_backend.bat
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import BACKEND_PORT, CORS_ORIGINS
from backend.api import parse as parse_api
from backend.api import knowledge as knowledge_api
from backend.api import chat as chat_api
from backend.api import chunks as chunks_api
from backend.state import state

# ---------------- 日志 ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时打印配置，嵌入模型可选预热。"""
    logger.info("=" * 60)
    logger.info("母婴护理 RAG 检索系统启动中...")
    logger.info("后端端口: %d, CORS: %s", BACKEND_PORT, CORS_ORIGINS)
    logger.info("嵌入模型: %s (1024维), 生成模型: %s", "bge-m3:latest", "qwen3:8b")
    logger.info("重排模型: bge-reranker-large (CPU 懒加载)")
    # 可选预热嵌入模型（失败不阻塞启动）
    try:
        _ = state.embedder.embed_query("warmup")
        logger.info("嵌入模型预热完成")
    except Exception as e:
        logger.warning("嵌入模型预热失败（Ollama 可能未启动）: %s", e)
    logger.info("系统就绪，监听端口 %d", BACKEND_PORT)
    logger.info("=" * 60)
    yield


# ---------------- 创建应用 ---------------- #
app = FastAPI(
    title="母婴护理 RAG 检索增强系统",
    description="千万级长文本垂直领域复杂版面分析与结构化切片（父子分块）RAG 检索增强系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- 注册路由 ---------------- #
app.include_router(parse_api.router)
app.include_router(knowledge_api.router)
app.include_router(chat_api.router)
app.include_router(chunks_api.router)


# ---------------- 健康检查 ---------------- #
@app.get("/health")
async def health():
    """健康检查端点（含 Ollama 状态与模型列表）。"""
    ollama_status = "unknown"
    ollama_models = []
    try:
        import requests as _req
        r = _req.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            ollama_status = "ok"
            data = r.json()
            ollama_models = [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        ollama_status = "down"
    return {
        "status": "ok",
        "service": "母婴护理 RAG 检索增强系统",
        "backend_port": BACKEND_PORT,
        "kb_count": len(state.knowledge_bases),
        "parsed_docs": len(state.parse_results),
        "ollama_status": ollama_status,
        "ollama_models": ollama_models,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=BACKEND_PORT,
        reload=False,
    )
