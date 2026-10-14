"""
表格提取器（TableExtractor）

基于 pdfplumber 的 page.find_tables() 定位表格区域，并把单元格数据
转换为 Markdown 表格格式（| 列1 | 列2 |）。

输出的每个表格 dict：
    {
        "page_number": int,
        "bbox": (x0, top, x1, bottom),
        "markdown": "| 列1 | 列2 |\\n| --- | --- |\\n| a | b |",
        "rows": [[cell, ...], ...],     # 原始二维数据
        "position_tag": "@@页码\\t左\\t右\\t上\\t下##",
    }
"""
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class TableExtractor:
    """从 pdfplumber.Page 中提取表格并转 Markdown。"""

    def extract_tables(
        self,
        page,
        page_number: int,
    ) -> List[Dict[str, Any]]:
        """
        在单页上查找所有表格。

        参数:
            page: pdfplumber.Page 对象
            page_number: 真实页码（从 1 开始）

        返回:
            表格 dict 列表（含 Markdown 文本、bbox、页码、位置标签）
        """
        tables_out: List[Dict[str, Any]] = []
        try:
            # pdfplumber 内置表格检测
            found = page.find_tables()
        except Exception as e:
            logger.warning("第 %d 页 find_tables 失败: %s", page_number, e)
            return tables_out

        for t in found:
            try:
                rows = t.extract()  # 二维列表，元素为单元格字符串或 None
            except Exception as e:
                logger.warning("第 %d 页表格 extract 失败: %s", page_number, e)
                continue
            if not rows:
                continue

            # 清洗单元格：None -> 空串，去掉换行
            cleaned_rows: List[List[str]] = []
            for row in rows:
                cleaned = []
                for cell in row:
                    if cell is None:
                        cleaned.append("")
                    else:
                        cleaned.append(" ".join(str(cell).split()))
                cleaned_rows.append(cleaned)

            # 去掉全空行
            cleaned_rows = [r for r in cleaned_rows if any(c.strip() for c in r)]
            if not cleaned_rows:
                continue

            markdown = self._rows_to_markdown(cleaned_rows)

            # 表格 bbox
            bbox = None
            try:
                if t.bbox is not None:
                    bbox = (float(t.bbox[0]), float(t.bbox[1]),
                            float(t.bbox[2]), float(t.bbox[3]))
            except Exception:
                bbox = None

            tag = self._make_position_tag(page_number, bbox)
            tables_out.append({
                "page_number": page_number,
                "bbox": list(bbox) if bbox else [0.0, 0.0, 0.0, 0.0],
                "markdown": markdown,
                "rows": cleaned_rows,
                "position_tag": tag,
            })
            logger.debug("第 %d 页提取表格: %d 行, %d 列",
                         page_number, len(cleaned_rows), len(cleaned_rows[0]) if cleaned_rows else 0)

        return tables_out

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #
    @staticmethod
    def _rows_to_markdown(rows: List[List[str]]) -> str:
        """
        把二维单元格数据转成 Markdown 表格。
        第一行作为表头，第二行为分隔行。
        """
        if not rows:
            return ""
        ncols = max(len(r) for r in rows)
        # 补齐每行列数
        norm = [r + [""] * (ncols - len(r)) for r in rows]

        header = norm[0]
        body = norm[1:] if len(norm) > 1 else []

        lines = []
        # 表头
        lines.append("| " + " | ".join(header) + " |")
        # 分隔行
        lines.append("| " + " | ".join(["---"] * ncols) + " |")
        # 数据行
        for r in body:
            lines.append("| " + " | ".join(r) + " |")
        return "\n".join(lines)

    @staticmethod
    def _make_position_tag(page: int, bbox) -> str:
        """生成位置标签 @@页码\\t左\\t右\\t上\\t下##。"""
        if bbox is None:
            return f"@@{page}\t0\t0\t0\t0##"
        x0, top, x1, bottom = bbox
        return f"@@{page}\t{x0:.1f}\t{x1:.1f}\t{top:.1f}\t{bottom:.1f}##"
