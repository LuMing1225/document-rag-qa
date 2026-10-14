"""
父子分块器（ParentChildChunker）

分块策略（Parent-Child Chunking）：
- 子文档 Child：约 300 tokens（中文约 450 字），用于稠密向量检索，粒度细、召回准
- 父文档 Parent：约 1200 tokens（中文约 1800 字），用于 LLM 上下文，信息全、上下文足
- 映射：每个 child 记录 parent_id；每个 parent 记录 child_ids 列表

聚合规则：
1. 按标题层级聚合：遇到 title 区域 → 先收尾当前父块，再以该标题开启新父块
2. 表格不切分：table 区域整块作为一个独立父块（不与正文拼接）
3. 长段落滑动窗口：正文累加到父块超过 1800 字 → 收尾并开启新父块
4. 父块内部再切成子块：子块 ≤ 450 字，重叠 50 字（滑动窗口）
"""
import logging
from typing import Any, Dict, List, Tuple

from backend.config import (
    CHILD_CHUNK_SIZE,
    PARENT_CHUNK_SIZE,
    CHUNK_OVERLAP,
)
from backend.models import ChildChunk, ParentChunk, TextChunk

logger = logging.getLogger(__name__)


class ParentChildChunker:
    """父子分块器。"""

    def __init__(
        self,
        child_size: int = CHILD_CHUNK_SIZE,
        parent_size: int = PARENT_CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP,
    ) -> None:
        self.child_size = child_size
        self.parent_size = parent_size
        self.overlap = overlap

    # ------------------------------------------------------------------ #
    # 公共接口
    # ------------------------------------------------------------------ #
    def chunk(
        self,
        text_chunks: List[TextChunk],
        doc_id: str = "doc",
    ) -> Tuple[List[ParentChunk], List[ChildChunk]]:
        """
        把版面文本块列表切分成父子块。

        参数:
            text_chunks: 按阅读顺序排好的 TextChunk（含 title/text/table）
            doc_id: 文档 id，用于生成 chunk 前缀

        返回:
            (parents, children)
        """
        # 第一阶段：按标题/表格/字数聚合出父块
        parent_specs: List[Dict[str, Any]] = self._build_parents(text_chunks)

        parents: List[ParentChunk] = []
        children: List[ChildChunk] = []

        for p_idx, spec in enumerate(parent_specs):
            parent_id = f"{doc_id}_p{p_idx:05d}"
            parent_text = spec["text"]

            parent = ParentChunk(
                parent_id=parent_id,
                text=parent_text,
                page_numbers=sorted(set(spec["page_numbers"])),
                heading_path=spec["heading_path"],
                layout_type=spec["layout_type"],
                metadata={
                    "doc_id": doc_id,
                    "position_tags": spec["position_tags"],
                },
                child_ids=[],
            )

            # 第二阶段：父块内部切成子块（滑动窗口）
            child_spans = self._split_text_sliding(
                parent_text, self.child_size, self.overlap
            )
            for c_idx, (seg, start, end) in enumerate(child_spans):
                child_id = f"{doc_id}_ch{p_idx:05d}_{c_idx:03d}"
                child = ChildChunk(
                    child_id=child_id,
                    parent_id=parent_id,
                    text=seg,
                    page_number=spec["page_numbers"][0] if spec["page_numbers"] else 0,
                    position_tag=spec["position_tags"][0] if spec["position_tags"] else "",
                    layout_type=spec["layout_type"],
                    heading_path=spec["heading_path"],
                )
                children.append(child)
                parent.child_ids.append(child_id)

            parents.append(parent)

        logger.info(
            "父子分块完成: 输入块=%d, 父块=%d, 子块=%d (child≤%d字, parent≤%d字, overlap=%d)",
            len(text_chunks), len(parents), len(children),
            self.child_size, self.parent_size, self.overlap,
        )
        return parents, children

    # ------------------------------------------------------------------ #
    # 父块聚合
    # ------------------------------------------------------------------ #
    def _build_parents(self, text_chunks: List[TextChunk]) -> List[Dict[str, Any]]:
        """
        按规则把 TextChunk 聚合成父块规格（尚未切子块）。

        每个父块规格:
            {
                "text": 拼接后的父块文本,
                "page_numbers": [页码...],
                "position_tags": [位置标签...],
                "heading_path": 标题路径,
                "layout_type": text/table/title,
            }
        """
        specs: List[Dict[str, Any]] = []

        # 当前缓冲中的片段
        cur_pieces: List[str] = []
        cur_pages: List[int] = []
        cur_tags: List[str] = []
        cur_heading = ""
        cur_layout = "text"

        def _flush():
            """把当前缓冲落成一个父块规格。"""
            nonlocal cur_pieces, cur_pages, cur_tags, cur_heading, cur_layout
            if not cur_pieces:
                return
            text = "\n".join(cur_pieces).strip()
            if not text:
                cur_pieces, cur_pages, cur_tags = [], [], []
                return
            specs.append({
                "text": text,
                "page_numbers": cur_pages[:],
                "position_tags": cur_tags[:],
                "heading_path": cur_heading,
                "layout_type": cur_layout,
            })
            cur_pieces, cur_pages, cur_tags = [], [], []

        for tc in text_chunks:
            content = tc.text.strip()
            if not content:
                continue

            if tc.layout_type == "title":
                # 标题 → 收尾当前缓冲，以该标题开启新父块
                _flush()
                cur_heading = content
                cur_layout = "title"
                cur_pieces.append(content)
                cur_pages.append(tc.page_number)
                cur_tags.append(tc.position_tag)

            elif tc.layout_type == "table":
                # 表格整块 → 收尾当前缓冲，表格独占一个父块
                _flush()
                specs.append({
                    "text": content,
                    "page_numbers": [tc.page_number],
                    "position_tags": [tc.position_tag],
                    "heading_path": tc.heading_path,
                    "layout_type": "table",
                })

            else:
                # 正文 → 累积；超长则先收尾
                if not cur_pieces:
                    # 新开缓冲，继承标题路径
                    cur_heading = tc.heading_path or cur_heading
                    cur_layout = "text"

                # 若已有内容且追加后超过父块上限 → 先收尾
                cur_len = sum(len(p) for p in cur_pieces)
                if cur_pieces and cur_len + len(content) > self.parent_size:
                    _flush()
                    cur_heading = tc.heading_path or cur_heading
                    cur_layout = "text"

                cur_pieces.append(content)
                cur_pages.append(tc.page_number)
                cur_tags.append(tc.position_tag)

        # 收尾最后一个缓冲
        _flush()
        return specs

    # ------------------------------------------------------------------ #
    # 子块滑动窗口切分
    # ------------------------------------------------------------------ #
    @staticmethod
    def _split_text_sliding(
        text: str,
        size: int,
        overlap: int,
    ) -> List[Tuple[str, int, int]]:
        """
        滑动窗口切分长文本为 ≤ size 字的片段，相邻片段重叠 overlap 字。

        返回: [(片段, 起始偏移, 结束偏移), ...]
        """
        n = len(text)
        if n <= size:
            return [(text, 0, n)] if text else []

        step = max(1, size - overlap)
        spans: List[Tuple[str, int, int]] = []
        start = 0
        while start < n:
            end = min(start + size, n)
            seg = text[start:end]
            spans.append((seg, start, end))
            if end == n:
                break
            start += step
        return spans
