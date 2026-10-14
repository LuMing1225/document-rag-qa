"""
系统配置：母婴护理垂直领域 RAG 后端

集中管理端口、模型路径、分块参数、检索超参等。
所有路径尽量使用 Path 表示，Windows 中文路径也能安全处理。
"""
import os
from pathlib import Path

# ------------------------------------------------------------------ #
# 路径配置
# ------------------------------------------------------------------ #
# 项目根目录（backend/ 的上一级）
BASE_DIR = Path(__file__).parent.parent

# 数据目录：上传文件、解析结果、向量库、裁剪图片
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PARSED_DIR = DATA_DIR / "parsed"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"
FIGURE_DIR = DATA_DIR / "figures"

# 启动时自动创建数据目录
for _d in [UPLOAD_DIR, PARSED_DIR, VECTORSTORE_DIR, FIGURE_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ #
# 服务端口
# ------------------------------------------------------------------ #
BACKEND_PORT = 8563        # FastAPI 后端端口
FRONTEND_PORT = 8523       # 前端页面端口（仅用于 CORS 白名单）

# ------------------------------------------------------------------ #
# Ollama 大模型服务配置
# ------------------------------------------------------------------ #
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = 180       # LLM 生成可能较慢，超时给宽一些

# 嵌入模型（通过 Ollama /api/embed 调用，GPU 由 Ollama 自行管理）
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3:latest")
EMBEDDING_DIM = 1024       # bge-m3 输出维度

# 生成模型（通过 Ollama /api/chat 调用）
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "qwen3:8b")

# ------------------------------------------------------------------ #
# 本地重排模型（cross-encoder，CPU 运行，把 8GB 显存留给 LLM）
# ------------------------------------------------------------------ #
RERANKER_PATH = os.getenv("RERANKER_PATH", str(BASE_DIR / "models" / "bge-reranker-large"))
RERANKER_DEVICE = os.getenv("RERANKER_DEVICE", "cpu")  # CPU运行，避免与Ollama LLM抢8GB显存
RERANKER_MAX_LEN = 256     # cross-encoder 输入最大长度（减小以提速）
USE_RERANKER = True         # 是否启用重排器（性能测试可通过参数关闭）

# ------------------------------------------------------------------ #
# 父子分块参数（单位：字符，中文约 1 字 ≈ 1.5~2 token）
# ------------------------------------------------------------------ #
CHILD_CHUNK_SIZE = 450     # 子块约 300 tokens（用于稠密向量检索）
PARENT_CHUNK_SIZE = 1800   # 父块约 1200 tokens（用于 LLM 上下文）
CHUNK_OVERLAP = 50         # 长段落滑动窗口重叠字数

# ------------------------------------------------------------------ #
# 检索与重排超参
# ------------------------------------------------------------------ #
TOP_K = 5                  # 最终返回的父文档数量
RECALL_K = 15              # 第一阶段子文档稠密召回数量
BETA = 0.4                 # 多向量评分权重：最终分 = β*稠密分 + (1-β)*重排分
SIMILARITY_THRESHOLD = 0.20  # 稠密相似度阈值（余弦，-1~1）

# ------------------------------------------------------------------ #
# 解析配置
# ------------------------------------------------------------------ #
DEFAULT_ZOOMIN = 3         # 页面渲染缩放比（用于裁剪图表）

# ------------------------------------------------------------------ #
# CORS 跨域配置
# ------------------------------------------------------------------ #
CORS_ORIGINS = [
    f"http://localhost:{FRONTEND_PORT}",
    f"http://127.0.0.1:{FRONTEND_PORT}",
    f"http://localhost:{BACKEND_PORT}",
    f"http://127.0.0.1:{BACKEND_PORT}",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
