"""
Pydantic 数据模型定义

面向"母婴护理"垂直领域 RAG 系统，核心数据结构：
- 版面区域 LayoutRegion：版面分析输出的最小区域
- TextChunk / ParentChunk / ChildChunk：父子分块体系
- ParseResult：一次 PDF 解析的完整结果
- RetrievedParent：检索阶段返回的父文档（含多种评分）
- QueryResponse：问答响应
"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
# 枚举
# ------------------------------------------------------------------ #
class ParseStatus(str, Enum):
    """文档解析状态。"""
    pending = "pending"
    parsing = "parsing"
    completed = "completed"
    failed = "failed"


class LayoutType(str, Enum):
    """版面区域类型。"""
    title = "title"      # 标题
    text = "text"        # 正文
    table = "table"      # 表格
    figure = "figure"    # 图片/插图


# ------------------------------------------------------------------ #
# 版面分析输出
# ------------------------------------------------------------------ #
class LayoutRegion(BaseModel):
    """
    版面分析器输出的一个区域。

    字段:
        type: title / text / table / figure
        bbox: (x0, top, x1, bottom) 页面坐标
        text: 区域文本（table 类型为 Markdown 表格）
        column: left / right / full（双栏时标注属于左栏还是右栏）
    """
    type: str = "text"
    bbox: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    text: str = ""
    column: str = "full"          # left / right / full
    page_number: int = 0


# ------------------------------------------------------------------ #
# 分块体系
# ------------------------------------------------------------------ #
class TextChunk(BaseModel):
    """通用文本块（版面分析后、父子分块前的中间形态）。"""
    chunk_id: str
    text: str
    page_number: int
    position_tag: str = ""        # @@页码\t左\t右\t上\t下##
    layout_type: str = "text"     # title/text/table/figure
    heading_path: str = ""        # 标题层级路径
    column: str = "full"          # left/right/full


class ParentChunk(BaseModel):
    """
    父文档块：约 1200 tokens（中文约 1800 字），送入 LLM 上下文。
    父文档不单独建向量，通过 child -> parent 映射间接被检索到。
    """
    parent_id: str
    text: str
    page_numbers: List[int] = Field(default_factory=list)   # 该父块涉及的页码
    child_ids: List[str] = Field(default_factory=list)    # 包含的子块 id
    heading_path: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    layout_type: str = "text"


class ChildChunk(BaseModel):
    """
    子文档块：约 300 tokens（中文约 450 字），用于稠密向量检索。
    每个 child 记录其所属 parent_id。
    """
    child_id: str
    parent_id: str
    text: str
    page_number: int
    position_tag: str = ""
    layout_type: str = "text"
    heading_path: str = ""


# ------------------------------------------------------------------ #
# 解析结果
# ------------------------------------------------------------------ #
class ParseResult(BaseModel):
    """一次 PDF 解析的完整结果。"""
    doc_id: str
    filename: str
    total_pages: int = 0
    status: ParseStatus = ParseStatus.pending
    chunks: List[TextChunk] = Field(default_factory=list)          # 版面文本块
    layout_regions: List[LayoutRegion] = Field(default_factory=list)  # 版面区域（可视化用）
    tables: List[Dict[str, Any]] = Field(default_factory=list)     # 提取到的表格（Markdown）
    full_text: str = ""
    parse_time: float = 0.0
    error: str = ""


# ------------------------------------------------------------------ #
# 知识库
# ------------------------------------------------------------------ #
class KnowledgeBase(BaseModel):
    """知识库元信息。"""
    kb_id: str
    name: str
    description: str = ""
    document_count: int = 0
    parent_count: int = 0         # 父块数量
    child_count: int = 0          # 子块数量
    created_at: str = ""


# ------------------------------------------------------------------ #
# 检索 / 问答
# ------------------------------------------------------------------ #
class QueryRequest(BaseModel):
    """RAG 问答请求。"""
    question: str
    kb_id: str = "default"
    top_k: int = 5
    stream: bool = False


class RetrievedParent(BaseModel):
    """
    检索阶段返回的父文档，包含三路评分拆解，便于前端调试展示。
    """
    parent_id: str
    text: str
    score: float = 0.0            # 最终融合分
    dense_score: float = 0.0      # 子文档稠密相似度（余弦）
    rerank_score: float = 0.0     # BGE-Reranker 相关性（0~1）
    page_numbers: List[int] = Field(default_factory=list)
    child_count: int = 0
    heading_path: str = ""
    layout_type: str = "text"


class QueryResponse(BaseModel):
    """RAG 问答响应。"""
    question: str
    answer: str
    retrieved_parents: List[RetrievedParent] = Field(default_factory=list)
    response_time: float = 0.0
    model_used: str = ""
