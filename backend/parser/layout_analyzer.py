"""
版面分析器（LayoutAnalyzer）

基于 pdfplumber 字符坐标的启发式版面分析，不依赖深度学习模型，适合本地低算力运行。

核心能力：
1. 字符按 y 坐标聚类成行，行按纵向间隙聚合成段落块
2. 双栏检测：计算页面中线附近是否存在大空白带，若左右两栏文本 x 范围基本不重叠则判定双栏
3. 阅读顺序：双栏时先读完左栏再读右栏；单栏时按从上到下、从左到右
4. 标题层级识别：字号偏大 / 加粗 / 行短 判定为 title
5. 图片区域识别：页面中大面积无文本条带判定为 figure

输出区域列表，每个区域为 dict：
    {
        "type": "title" | "text" | "figure",
        "bbox": (x0, top, x1, bottom),
        "text": "...",
        "column": "left" | "right" | "full",
    }
"""
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class LayoutAnalyzer:
    """单页版面分析器。"""

    # 行聚类参数（单位 pt）
    LINE_Y_TOL = 3.0          # 同一行的 y 坐标容差
    BLOCK_Y_GAP = 8.0         # 段落之间的最小纵向间隙
    X_GAP_SPLIT = 20.0        # 同一 y 行内横向间隙超过此值则拆为两段（识别左右双栏/并排文本框）

    # 双栏检测参数
    MID_BAND_HALF = 30.0      # 中线空白带半宽（pt）
    MAX_CROSS_RATIO = 0.15    # 跨中线行占比低于此值才可能是双栏
    MIN_SIDE_RATIO = 0.20     # 左右两侧文本占比下限，过低不算双栏

    # 标题判定参数
    TITLE_MIN_SIZE = 10.5     # 字号 >= 此值且行短 → 标题（正文约 9~10pt）
    TITLE_MAX_LEN = 60        # 标题最大字数
    BOLD_TITLE_MAX_LEN = 40   # 加粗标题最大字数

    # 标题文本模式：匹配章节编号类标题（如 "第一章 ..."、"1.1 ..."、"2.3 ..."、"附录A"）
    HEADING_PATTERN = re.compile(
        r"^\s*("
        r"第[一二三四五六七八九十百0-9]+[章节部分回编篇]"   # 第一章 / 第二节 / 第三部分
        r"|\d+(?:\.\d+){1,3}"                              # 1.1 / 1.2.3（多级数字编号）
        r"|[一二三四五六七八九十]+[、.．]\s*\S"             # 一、二、
        r"|附录[0-9A-Za-z一二三四五六七八九十]*"           # 附录 / 附录A
        r")"
    )

    def analyze_page(
        self,
        chars: List[Dict[str, Any]],
        page_width: float,
        page_height: float,
    ) -> List[Dict[str, Any]]:
        """
        分析单页版面，返回按阅读顺序排好的区域列表。

        参数:
            chars: pdfplumber 提取的字符，每个含 x0/x1/top/bottom/text/size/fontname
            page_width: 页面宽度（pt）
            page_height: 页面高度（pt）
        """
        # 没有文本层 → 整页视为图片区域
        if not chars:
            return [{
                "type": "figure",
                "bbox": (0.0, 0.0, page_width, page_height),
                "text": "",
                "column": "full",
            }]

        # 1. 字符聚类成行
        lines = self._cluster_lines(chars)
        if not lines:
            return [{
                "type": "figure",
                "bbox": (0.0, 0.0, page_width, page_height),
                "text": "",
                "column": "full",
            }]

        # 2. 双栏检测
        is_two_column = self._detect_two_column(lines, page_width)
        logger.debug("页面 %.0fx%.0f, 双栏=%s", page_width, page_height, is_two_column)

        # 3. 行聚类成段落块（按 column 归属）
        blocks = self._cluster_blocks(lines, page_width, is_two_column)

        # 4. 每个块判定 title / text
        regions: List[Dict[str, Any]] = []
        for blk in blocks:
            btype = self._classify_block(blk)
            x0 = min(c["x0"] for c in blk["chars"])
            x1 = max(c["x1"] for c in blk["chars"])
            top = min(c["top"] for c in blk["chars"])
            bottom = max(c["bottom"] for c in blk["chars"])
            regions.append({
                "type": btype,
                "bbox": (x0, top, x1, bottom),
                "text": blk["text"],
                "column": blk.get("column", "full"),
            })

        # 5. 大面积无文本条带 → figure 区域
        figure_regions = self._detect_figure_regions(regions, page_width, page_height)
        regions.extend(figure_regions)

        # 6. 按阅读顺序排序
        regions = self._sort_by_reading_order(regions, page_width, is_two_column)
        return regions

    # ------------------------------------------------------------------ #
    # 行 / 块聚类
    # ------------------------------------------------------------------ #
    def _cluster_lines(self, chars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        把字符按 top 坐标聚类成行；同一 y 行内若出现大于 X_GAP_SPLIT 的横向间隙，
        则拆成两段（解决左右双栏/并排文本框被拼成一行的问题）。
        """
        sorted_chars = sorted(chars, key=lambda c: (c["top"], c["x0"]))

        # 第一步：按 y 坐标聚成 y 组
        y_groups: List[Dict[str, Any]] = []
        for ch in sorted_chars:
            placed = False
            for g in y_groups:
                if abs(ch["top"] - g["_y"]) <= self.LINE_Y_TOL:
                    g["chars"].append(ch)
                    g["_y"] = sum(c["top"] for c in g["chars"]) / len(g["chars"])
                    placed = True
                    break
            if not placed:
                y_groups.append({"_y": ch["top"], "chars": [ch]})

        # 第二步：每个 y 组内按横向大间隙拆成段
        result: List[Dict[str, Any]] = []
        for g in y_groups:
            gchars = sorted(g["chars"], key=lambda c: c["x0"])
            segments: List[List[Dict[str, Any]]] = []
            current: List[Dict[str, Any]] = [gchars[0]]
            for i in range(1, len(gchars)):
                gap = gchars[i]["x0"] - current[-1]["x1"]
                if gap > self.X_GAP_SPLIT:
                    segments.append(current)
                    current = [gchars[i]]
                else:
                    current.append(gchars[i])
            segments.append(current)

            for seg in segments:
                text = "".join(c["text"] for c in seg)
                result.append({
                    "chars": seg,
                    "text": text,
                    "top": min(c["top"] for c in seg),
                    "bottom": max(c["bottom"] for c in seg),
                    "x0": min(c["x0"] for c in seg),
                    "x1": max(c["x1"] for c in seg),
                })
        result.sort(key=lambda l: (round(l["top"] / 3), l["x0"]))
        return result

    def _cluster_blocks(
        self,
        lines: List[Dict[str, Any]],
        page_width: float,
        is_two_column: bool,
    ) -> List[Dict[str, Any]]:
        """
        把相邻行聚合成段落块。
        双栏时：先按 column（left/right）分组，再各自按 y 间隙聚类。
        """
        mid_x = page_width / 2

        # 先给每行打 column 标签
        for ln in lines:
            cx = (ln["x0"] + ln["x1"]) / 2
            if is_two_column:
                ln["column"] = "left" if cx < mid_x else "right"
            else:
                ln["column"] = "full"

        if not is_two_column:
            return self._group_lines_into_blocks(lines)

        # 双栏：分别对左栏、右栏聚类
        left_lines = [l for l in lines if l["column"] == "left"]
        right_lines = [l for l in lines if l["column"] == "right"]
        blocks = []
        blocks.extend(self._group_lines_into_blocks(left_lines, column="left"))
        blocks.extend(self._group_lines_into_blocks(right_lines, column="right"))
        return blocks

    def _group_lines_into_blocks(
        self,
        lines: List[Dict[str, Any]],
        column: str = "full",
    ) -> List[Dict[str, Any]]:
        """
        把一组行按纵向间隙聚合成段落块。
        关键：若两行处于同一视觉行（y 重叠）但横向间隙很大（并排栏），
        则强制不合并，避免左栏标题与右栏正文粘成一块。
        """
        if not lines:
            return []
        # 先按近似行（top 网格）再按 x0 排序，保证同一行左栏在前、右栏在后
        lines = sorted(lines, key=lambda l: (round(l["top"] / 3), l["x0"]))
        blocks: List[Dict[str, Any]] = []
        current = [lines[0]]
        for i in range(1, len(lines)):
            prev = current[-1]
            cur = lines[i]
            gap = cur["top"] - prev["bottom"]

            # 同一视觉行（y 有重叠）但横向间隙大 → 并行栏，不合并
            same_row = cur["top"] <= prev["bottom"] + self.LINE_Y_TOL
            x_gap = cur["x0"] - prev["x1"]
            parallel_column = same_row and x_gap > self.X_GAP_SPLIT

            if gap > self.BLOCK_Y_GAP or parallel_column:
                blocks.append(self._make_block(current, column))
                current = [cur]
            else:
                current.append(cur)
        blocks.append(self._make_block(current, column))
        return blocks

    @staticmethod
    def _make_block(lines: List[Dict[str, Any]], column: str) -> Dict[str, Any]:
        """合并多行成一个文本块。"""
        chars: List[Dict[str, Any]] = []
        for ln in lines:
            chars.extend(ln["chars"])
        text = "\n".join(ln["text"] for ln in lines)
        return {
            "chars": chars,
            "text": text,
            "top": min(ln["top"] for ln in lines),
            "bottom": max(ln["bottom"] for ln in lines),
            "x0": min(ln["x0"] for ln in lines),
            "x1": max(ln["x1"] for ln in lines),
            "column": column,
        }

    # ------------------------------------------------------------------ #
    # 双栏检测
    # ------------------------------------------------------------------ #
    def _detect_two_column(self, lines: List[Dict[str, Any]], page_width: float) -> bool:
        """
        双栏检测：
        1. 计算页面中线 mid_x = page_width / 2
        2. 统计跨越中线的行占比；若占比很低（文本不越中线），说明左右两栏 x 范围不重叠
        3. 统计中线空白带内的文本覆盖率；若很低，说明中间有大空白带
        4. 左右两侧都有足够文本
        同时满足 → 双栏
        """
        if not lines or page_width < 100:
            return False

        mid_x = page_width / 2
        n = len(lines)

        # 跨中线的行
        cross = sum(1 for ln in lines if ln["x0"] < mid_x < ln["x1"])
        cross_ratio = cross / n

        # 左右两侧文本行数量
        left_cnt = sum(1 for ln in lines if (ln["x0"] + ln["x1"]) / 2 < mid_x)
        right_cnt = n - left_cnt
        left_ratio = left_cnt / n
        right_ratio = right_cnt / n

        # 中线空白带 [mid_x - band, mid_x + band] 的文本覆盖率
        band_x0 = mid_x - self.MID_BAND_HALF
        band_x1 = mid_x + self.MID_BAND_HALF
        band_width = band_x1 - band_x0
        covered = 0.0
        for ln in lines:
            ox0 = max(ln["x0"], band_x0)
            ox1 = min(ln["x1"], band_x1)
            if ox1 > ox0:
                covered += (ox1 - ox0)
        # 近似：用页面高度归一化覆盖面积
        page_h = max(ln["bottom"] for ln in lines) - min(ln["top"] for ln in lines)
        band_coverage = covered / (band_width * page_h + 1e-6) if page_h > 0 else 1.0

        is_two = (
            cross_ratio <= self.MAX_CROSS_RATIO
            and left_ratio >= self.MIN_SIDE_RATIO
            and right_ratio >= self.MIN_SIDE_RATIO
            and band_coverage < 0.25
        )
        logger.debug(
            "双栏检测: cross_ratio=%.2f left=%.2f right=%.2f band_cov=%.2f -> %s",
            cross_ratio, left_ratio, right_ratio, band_coverage, is_two,
        )
        return is_two

    # ------------------------------------------------------------------ #
    # 标题 / 正文 判定
    # ------------------------------------------------------------------ #
    def _classify_block(self, block: Dict[str, Any]) -> str:
        """
        判定块类型：title / text。
        标题判定三路：
        1) 章节编号模式（"第一章"、"1.1"、"2.3"、"附录A" 等）且行短
        2) 字号偏大（>=10.5pt）且行短（正文约 9~10pt）
        3) 加粗且行短
        """
        chars = block["chars"]
        if not chars:
            return "text"
        avg_size = sum(c.get("size", 10.0) for c in chars) / len(chars)
        text_stripped = block["text"].strip()
        text_len = len(text_stripped)
        has_bold = any("bold" in c.get("fontname", "").lower() for c in chars)

        # 1) 章节编号模式优先（如 "1.1 母乳喂养的重要性"、"第一章 新生儿喂养基础"）
        #    限制行长，避免把以数字开头的正文长句误判为标题
        if self.HEADING_PATTERN.match(text_stripped) and text_len <= self.TITLE_MAX_LEN:
            return "title"
        # 2) 字号明显偏大且行短 → 一级/二级标题
        if avg_size >= self.TITLE_MIN_SIZE and text_len <= self.TITLE_MAX_LEN:
            return "title"
        # 3) 加粗且行短 → 小节标题
        if has_bold and text_len <= self.BOLD_TITLE_MAX_LEN:
            return "title"
        return "text"

    # ------------------------------------------------------------------ #
    # 图片区域识别
    # ------------------------------------------------------------------ #
    def _detect_figure_regions(
        self,
        regions: List[Dict[str, Any]],
        page_width: float,
        page_height: float,
    ) -> List[Dict[str, Any]]:
        """把页面纵向分成条带，文本覆盖率极低的条带合并为 figure 区域。"""
        text_boxes = [r["bbox"] for r in regions if r["type"] != "figure"]
        if not text_boxes:
            return []

        n_strips = 20
        strip_h = page_height / n_strips
        blank_strips: List[int] = []
        for i in range(n_strips):
            s_top = i * strip_h
            s_bottom = s_top + strip_h
            covered = 0.0
            for (x0, t, x1, b) in text_boxes:
                if b < s_top or t > s_bottom:
                    continue
                oh = min(b, s_bottom) - max(t, s_top)
                if oh > 0:
                    covered += (x1 - x0)
            coverage = covered / (page_width * strip_h + 1e-6)
            if coverage < 0.05:
                blank_strips.append(i)

        if not blank_strips:
            return []

        figures: List[Dict[str, Any]] = []
        start = blank_strips[0]
        prev = blank_strips[0]
        for idx in blank_strips[1:]:
            if idx == prev + 1:
                prev = idx
                continue
            f_top = start * strip_h
            f_bottom = (prev + 1) * strip_h
            if (f_bottom - f_top) > page_height * 0.05:
                figures.append({
                    "type": "figure",
                    "bbox": (0.0, f_top, page_width, f_bottom),
                    "text": "",
                    "column": "full",
                })
            start = idx
            prev = idx
        f_top = start * strip_h
        f_bottom = (prev + 1) * strip_h
        if (f_bottom - f_top) > page_height * 0.05:
            figures.append({
                "type": "figure",
                "bbox": (0.0, f_top, page_width, f_bottom),
                "text": "",
                "column": "full",
            })
        return figures

    # ------------------------------------------------------------------ #
    # 阅读顺序排序
    # ------------------------------------------------------------------ #
    def _sort_by_reading_order(
        self,
        regions: List[Dict[str, Any]],
        page_width: float,
        is_two_column: bool,
    ) -> List[Dict[str, Any]]:
        """
        双栏：左栏所有区域按 top 排完，再排右栏（先左后右）。
        单栏：按 top（四舍五入到 10pt 网格）再按 x0 排序。
        figure 区域归到它所在栏的对应位置。
        """
        if not is_two_column:
            regions.sort(key=lambda r: (round(r["bbox"][1] / 10), r["bbox"][0]))
            return regions

        mid_x = page_width / 2

        def _col(r: Dict[str, Any]) -> str:
            if r["column"] in ("left", "right"):
                return r["column"]
            # figure 等未标注的按中心 x 归栏
            cx = (r["bbox"][0] + r["bbox"][2]) / 2
            return "left" if cx < mid_x else "right"

        left = sorted(
            [r for r in regions if _col(r) == "left"],
            key=lambda r: (round(r["bbox"][1] / 10), r["bbox"][0]),
        )
        right = sorted(
            [r for r in regions if _col(r) == "right"],
            key=lambda r: (round(r["bbox"][1] / 10), r["bbox"][0]),
        )
        return left + right
