"""
PDF 解析器（PDFParser）

编排 pdfplumber（字符坐标 + 表格检测）与 pypdfium2（页面渲染 / 图表裁剪）：
1. 逐页提取字符（含 x0/x1/top/bottom/text/size/fontname）
2. 逐页调用 LayoutAnalyzer 做版面分析（双栏 / 标题 / 正文 / 图片区域）
3. 逐页调用 TableExtractor 提取表格并转 Markdown
4. 过滤掉落在表格 bbox 内的文本区域，避免重复
5. 按阅读顺序拼接，维护标题层级路径 heading_path
6. 输出 ParseResult：chunks（TextChunk）、layout_regions（可视化）、tables、full_text
"""
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

from backend.config import DEFAULT_ZOOMIN, FIGURE_DIR
from backend.models import (
    LayoutRegion,
    ParseResult,
    ParseStatus,
    TextChunk,
)
from backend.parser.layout_analyzer import LayoutAnalyzer
from backend.parser.table_extractor import TableExtractor

logger = logging.getLogger(__name__)


class PDFParser:
    """母婴护理 PDF 解析器。"""

    def __init__(self, zoomin: int = DEFAULT_ZOOMIN) -> None:
        self.zoomin = zoomin
        self.layout_analyzer = LayoutAnalyzer()
        self.table_extractor = TableExtractor()

    # ------------------------------------------------------------------ #
    # 公共接口
    # ------------------------------------------------------------------ #
    def parse(self, pdf_path: str, doc_id: str = "doc") -> ParseResult:
        """
        完整解析流程，返回 ParseResult。

        参数:
            pdf_path: PDF 文件路径
            doc_id: 文档唯一 id
        """
        t0 = time.time()
        pdf_path = str(pdf_path)
        filename = Path(pdf_path).name
        logger.info("开始解析 PDF: %s (doc_id=%s)", filename, doc_id)

        result = ParseResult(
            doc_id=doc_id,
            filename=filename,
            total_pages=0,
            status=ParseStatus.parsing,
        )

        try:
            # 预渲染所有页面（用于图表裁剪）
            page_images: List[Image.Image] = []
            try:
                pdf_doc = pdfium.PdfDocument(pdf_path)
                n_pages = len(pdf_doc)
                for i in range(n_pages):
                    bitmap = pdf_doc[i].render(scale=self.zoomin)
                    page_images.append(bitmap.to_pil().convert("RGB"))
                pdf_doc.close()
            except Exception as e:
                logger.warning("pypdfium2 渲染失败，图表裁剪将被跳过: %s", e)

            chunks: List[TextChunk] = []
            layout_regions: List[LayoutRegion] = []
            tables_all: List[Dict[str, Any]] = []
            full_text_parts: List[str] = []
            chunk_idx = 0
            heading_stack: List[str] = []

            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                result.total_pages = total_pages

                for i, page in enumerate(pdf.pages):
                    page_number = i + 1
                    page_w = float(page.width)
                    page_h = float(page.height)

                    # ---- 1. 提取字符 ----
                    chars: List[Dict[str, Any]] = []
                    for ch in page.chars:
                        chars.append({
                            "x0": ch["x0"],
                            "x1": ch["x1"],
                            "top": ch["top"],
                            "bottom": ch["bottom"],
                            "text": ch["text"],
                            "size": ch.get("size", 10.0),
                            "fontname": ch.get("fontname", ""),
                        })

                    # ---- 2. 表格提取 ----
                    page_tables = self.table_extractor.extract_tables(page, page_number)
                    tables_all.extend(page_tables)
                    table_bboxes = [tuple(t["bbox"]) for t in page_tables]

                    # ---- 3. 版面分析（文本 / 标题 / 图片区域） ----
                    regions = self.layout_analyzer.analyze_page(
                        chars, page_w, page_h
                    )

                    # ---- 4. 过滤掉落在表格 bbox 内的文本区域 ----
                    filtered: List[Dict[str, Any]] = []
                    for reg in regions:
                        if reg["type"] in ("text", "title") and self._inside_any_table(
                            reg["bbox"], table_bboxes
                        ):
                            continue
                        filtered.append(reg)

                    # ---- 5. 先记录版面区域（含表格），用于可视化 ----
                    for reg in filtered:
                        layout_regions.append(LayoutRegion(
                            type=reg["type"],
                            bbox=list(reg["bbox"]),
                            text=reg["text"],
                            column=reg.get("column", "full"),
                            page_number=page_number,
                        ))
                    for t in page_tables:
                        layout_regions.append(LayoutRegion(
                            type="table",
                            bbox=t["bbox"],
                            text=t["markdown"],
                            column="full",
                            page_number=page_number,
                        ))

                    # ---- 6. 裁剪图表区域为 PNG（可选，非致命） ----
                    for reg in filtered:
                        if reg["type"] == "figure" and i < len(page_images):
                            self._crop_figure(
                                page_images[i], reg["bbox"], page_w, page_h,
                                doc_id, page_number,
                            )

                    # ---- 7. 构造 TextChunk（阅读顺序已在 analyzer 内排好） ----
                    for reg in filtered:
                        text = reg["text"].strip()
                        if not text:
                            continue
                        if reg["type"] == "figure":
                            continue  # 纯图片区域不入文本块

                        x0, top, x1, bottom = reg["bbox"]
                        tag = self._make_position_tag(page_number, x0, x1, top, bottom)

                        # 维护标题层级路径
                        if reg["type"] == "title":
                            heading_stack = [text]
                            heading_path = text
                            layout_type = "title"
                        else:
                            heading_path = " > ".join(heading_stack) if heading_stack else ""
                            layout_type = "text"

                        chunks.append(TextChunk(
                            chunk_id=f"{doc_id}_c{chunk_idx:05d}",
                            text=text,
                            page_number=page_number,
                            position_tag=tag,
                            layout_type=layout_type,
                            heading_path=heading_path,
                            column=reg.get("column", "full"),
                        ))
                        chunk_idx += 1
                        full_text_parts.append(f"[第{page_number}页] {text}")

                    # ---- 8. 表格整块入 chunks（layout_type=table） ----
                    for t in page_tables:
                        md = t["markdown"].strip()
                        if not md:
                            continue
                        chunks.append(TextChunk(
                            chunk_id=f"{doc_id}_t{chunk_idx:05d}",
                            text=md,
                            page_number=page_number,
                            position_tag=t["position_tag"],
                            layout_type="table",
                            heading_path=" > ".join(heading_stack) if heading_stack else "",
                            column="full",
                        ))
                        chunk_idx += 1
                        full_text_parts.append(f"[第{page_number}页|表格]\n{md}")

            result.chunks = chunks
            result.layout_regions = layout_regions
            result.tables = tables_all
            result.full_text = "\n\n".join(full_text_parts)
            result.status = ParseStatus.completed
            result.parse_time = round(time.time() - t0, 2)

            logger.info(
                "解析完成: doc=%s, pages=%d, chunks=%d, regions=%d, tables=%d, 用时=%.2fs",
                doc_id, result.total_pages, len(chunks),
                len(layout_regions), len(tables_all), result.parse_time,
            )
            return result

        except Exception as e:
            logger.exception("PDF 解析失败: %s", e)
            result.status = ParseStatus.failed
            result.error = str(e)
            result.parse_time = round(time.time() - t0, 2)
            return result

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #
    @staticmethod
    def _inside_any_table(
        bbox: Tuple[float, float, float, float],
        table_bboxes: List[Tuple[float, float, float, float]],
    ) -> bool:
        """判断某个区域的中心是否落在任一表格 bbox 内。"""
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        for (tx0, ttop, tx1, tbottom) in table_bboxes:
            if tx0 <= cx <= tx1 and ttop <= cy <= tbottom:
                return True
        return False

    def _crop_figure(
        self,
        pil_image: Image.Image,
        bbox: Tuple[float, float, float, float],
        page_width: float,
        page_height: float,
        doc_id: str,
        page_number: int,
    ) -> Optional[str]:
        """裁剪 figure 区域保存为 PNG（失败不影响主流程）。"""
        try:
            x0, top, x1, bottom = bbox
            px0 = int(max(0, x0) * self.zoomin)
            py0 = int(max(0, top) * self.zoomin)
            px1 = int(min(page_width, x1) * self.zoomin)
            py1 = int(min(page_height, bottom) * self.zoomin)
            if px1 - px0 < 60 or py1 - py0 < 60:
                return None
            cropped = pil_image.crop((px0, py0, px1, py1))
            FIGURE_DIR.mkdir(parents=True, exist_ok=True)
            out = FIGURE_DIR / f"{doc_id}_p{page_number}_{abs(hash(bbox)) % 100000}.png"
            cropped.save(out, "PNG")
            return str(out)
        except Exception as e:
            logger.debug("裁剪图表失败（忽略）: %s", e)
            return None

    @staticmethod
    def _make_position_tag(
        page: int, x0: float, x1: float, top: float, bottom: float
    ) -> str:
        """生成位置标签 @@页码\\t左\\t右\\t上\\t下##。"""
        return f"@@{page}\t{x0:.1f}\t{x1:.1f}\t{top:.1f}\t{bottom:.1f}##"
