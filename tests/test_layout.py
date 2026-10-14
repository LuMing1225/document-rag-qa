"""
版面分析测试
验证：双栏阅读顺序、表格提取、标题层级、单栏处理
"""
import pytest


def detect_and_order_columns(text_blocks, page_width=560):
    """
    双栏检测与阅读顺序重排（坐标启发式算法）
    输入: text_blocks = [{bbox, text, top, x0, ...}, ...]
    输出: 按正确阅读顺序排列的文本块列表
    """
    mid_x = page_width / 2
    left_blocks = [b for b in text_blocks if b["x0"] < mid_x]
    right_blocks = [b for b in text_blocks if b["x0"] >= mid_x]

    is_double = len(left_blocks) > 2 and len(right_blocks) > 2

    if is_double:
        left_sorted = sorted(left_blocks, key=lambda b: b["top"])
        right_sorted = sorted(right_blocks, key=lambda b: b["top"])
        return left_sorted + right_sorted, True
    else:
        sorted_blocks = sorted(text_blocks, key=lambda b: (b["top"], b["x0"]))
        return sorted_blocks, False


def extract_table_to_markdown(table_rows):
    """将表格行数据转换为Markdown格式"""
    if not table_rows:
        return ""
    header = table_rows[0]
    lines = []
    lines.append("| " + " | ".join(str(c) if c else "" for c in header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for row in table_rows[1:]:
        lines.append("| " + " | ".join(str(c) if c else "" for c in row) + " |")
    return "\n".join(lines)


def detect_heading_levels(text_blocks):
    """根据字体大小识别标题层级"""
    sizes = [b.get("font_size", 11) for b in text_blocks]
    if not sizes:
        return []
    max_size = max(sizes)
    min_size = min(sizes)
    levels = []
    for b in text_blocks:
        fs = b.get("font_size", 11)
        if fs >= 16:
            level = 1  # H1 大标题
        elif fs >= 13:
            level = 2  # H2 小节标题
        elif fs > 11:
            level = 3  # H3 小标题
        else:
            level = 0  # 正文（默认字号约11）
        levels.append({"text": b["text"], "heading_level": level})
    return levels


class TestDoubleColumnFlow:
    """测试双栏阅读顺序拼接"""

    def test_double_column_flow(self, sample_text_blocks_double_column):
        """验证双栏PDF能正确按阅读顺序拼接：先左栏全部，再右栏全部"""
        ordered, is_double = detect_and_order_columns(sample_text_blocks_double_column)

        # 应该识别为双栏
        assert is_double is True

        # 前3个应该是左栏内容（x0=72）
        for i in range(3):
            assert ordered[i]["x0"] == 72, f"第{i}个块应该在左栏"

        # 后3个应该是右栏内容（x0=300）
        for i in range(3, 6):
            assert ordered[i]["x0"] == 300, f"第{i}个块应该在右栏"

        # 阅读顺序：左栏标题→左栏第一段→左栏第二段→右栏标题→...
        assert ordered[0]["text"] == "左栏标题"
        assert ordered[3]["text"] == "右栏标题"

    def test_double_column_content_continuity(self, sample_text_blocks_double_column):
        """验证双栏内文本按top坐标垂直排列"""
        ordered, _ = detect_and_order_columns(sample_text_blocks_double_column)

        # 左栏内部按top排序
        left_in_order = ordered[:3]
        tops = [b["top"] for b in left_in_order]
        assert tops == sorted(tops), "左栏内应按top坐标从上到下排列"

        # 右栏内部按top排序
        right_in_order = ordered[3:]
        tops = [b["top"] for b in right_in_order]
        assert tops == sorted(tops), "右栏内应按top坐标从上到下排列"


class TestTableDataRetrieval:
    """测试表格数据提取"""

    def test_table_data_retrieval(self, sample_table_data):
        """验证表格数据能正确提取为Markdown格式"""
        md = extract_table_to_markdown(sample_table_data)

        # Markdown表格应包含表头分隔线
        assert "---" in md

        # 应包含所有行数据
        assert "月龄" in md
        assert "0-1周" in md
        assert "8-12次" in md
        assert "10-30" in md
        assert "1-4周" in md

        # 表格行数 = 表头1行 + 数据2行
        lines = md.strip().split("\n")
        assert len(lines) == 4  # header + separator + 2 data rows

    def test_table_markdown_format(self, sample_table_data):
        """验证Markdown表格格式正确性"""
        md = extract_table_to_markdown(sample_table_data)
        lines = md.strip().split("\n")

        # 每行以|开头和结尾
        for line in lines:
            assert line.startswith("|"), f"行应以|开头: {line}"
            assert line.endswith("|"), f"行应以|结尾: {line}"

        # 分隔行
        assert "---" in lines[1]


class TestHeadingHierarchy:
    """测试标题层级识别"""

    def test_heading_hierarchy(self):
        """验证标题层级识别：H1/H2/正文区分正确"""
        blocks = [
            {"text": "第一章", "font_size": 18, "top": 100, "x0": 72},
            {"text": "1.1 母乳喂养", "font_size": 14, "top": 150, "x0": 72},
            {"text": "母乳是最好的食物", "font_size": 11, "top": 200, "x0": 72},
        ]
        levels = detect_heading_levels(blocks)

        assert levels[0]["heading_level"] == 1, "大字号应为H1"
        assert levels[1]["heading_level"] == 2, "中字号应为H2"
        assert levels[2]["heading_level"] == 0, "小字号应为正文"

    def test_heading_path_building(self):
        """验证标题路径拼接"""
        headings = [
            {"text": "第一章 新生儿喂养基础", "heading_level": 1},
            {"text": "1.1 母乳喂养的重要性", "heading_level": 2},
        ]
        path_parts = []
        for h in headings:
            path_parts.append(h["text"])
        heading_path = " > ".join(path_parts)

        assert heading_path == "第一章 新生儿喂养基础 > 1.1 母乳喂养的重要性"


class TestSingleColumn:
    """测试单栏排版处理"""

    def test_single_column(self, sample_text_blocks_single_column):
        """验证单栏排版：按top坐标从上到下排列，不做栏分组"""
        ordered, is_double = detect_and_order_columns(sample_text_blocks_single_column)

        # 应该识别为单栏
        assert is_double is False

        # 按top坐标排序
        assert ordered[0]["text"] == "章节标题"  # top=100
        assert ordered[1]["text"] == "正文第一段"  # top=130
        assert ordered[2]["text"] == "正文第二段"  # top=160

    def test_single_column_order(self, sample_text_blocks_single_column):
        """验证单栏文本按垂直位置正确排序"""
        ordered, _ = detect_and_order_columns(sample_text_blocks_single_column)
        tops = [b["top"] for b in ordered]
        assert tops == sorted(tops), "单栏应按top坐标排序"
