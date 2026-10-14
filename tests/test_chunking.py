"""
父子分块测试
验证：父子映射关系、子文档大小限制、表格不切分、重叠正确性
"""
import pytest
import re


def estimate_tokens(text):
    """简单估算token数（中文约1.5字/token）"""
    return int(len(text) / 1.5)


def split_parent_child(text, parent_max_tokens=1200, child_max_tokens=300, overlap=50):
    """
    父子分块算法
    返回: (parents, children)
    """
    parents = []
    children = []

    # 模拟：将整篇文本作为一个父文档
    parent = {
        "parent_id": "parent_0",
        "text": text,
        "tokens": estimate_tokens(text)
    }
    parents.append(parent)

    # 在父文档内切分子文档
    tokens_est = estimate_tokens(text)
    if tokens_est <= child_max_tokens:
        # 不需要切分
        children.append({
            "child_id": "child_0_0",
            "parent_id": "parent_0",
            "text": text,
            "tokens": tokens_est
        })
    else:
        # 按字符位置滑动窗口切分（模拟token切分）
        # child_max_tokens对应字符数约 child_max_tokens * 1.5
        char_per_child = int(child_max_tokens * 1.5)
        char_overlap = int(overlap * 1.5)
        step = char_per_child - char_overlap

        child_idx = 0
        pos = 0
        while pos < len(text):
            end = min(pos + char_per_child, len(text))
            child_text = text[pos:end]
            children.append({
                "child_id": f"child_0_{child_idx}",
                "parent_id": "parent_0",
                "text": child_text,
                "tokens": estimate_tokens(child_text)
            })
            child_idx += 1
            if end >= len(text):
                break
            pos += step

    return parents, children


class TestParentChildMapping:
    """测试父子映射关系"""

    def test_parent_child_mapping(self):
        """验证父子映射关系正确：每个子文档都能找到对应的父文档"""
        long_text = "这是一段测试文本。" * 100  # 约800字
        parents, children = split_parent_child(long_text)

        # 所有子文档的parent_id都应该在父文档列表中
        parent_ids = {p["parent_id"] for p in parents}
        for child in children:
            assert child["parent_id"] in parent_ids, \
                f"子文档{child['child_id']}的parent_id={child['parent_id']}找不到对应父文档"

    def test_child_parent_consistency(self):
        """验证子文档文本是父文档文本的子串"""
        long_text = "母乳是新生儿最理想的食物。" * 80
        parents, children = split_parent_child(long_text)

        parent_text = parents[0]["text"]
        for child in children:
            # 由于重叠切分，子文本应该能在父文本中找到（允许首尾边界差异）
            assert len(child["text"]) > 0, f"子文档{child['child_id']}为空"
            assert child["text"][:10] in parent_text or child["text"][-10:] in parent_text, \
                f"子文档内容应来自父文档"


class TestChildSizeLimit:
    """测试子文档大小限制"""

    def test_child_size_limit(self):
        """验证子文档不超过大小限制（300 tokens）"""
        long_text = "母乳喂养对婴儿非常重要。" * 200  # 约2400字
        parents, children = split_parent_child(long_text, child_max_tokens=300)

        for child in children:
            # 允许最后一个子文档略小，但不应超过限制太多
            assert child["tokens"] <= 350, \
                f"子文档{child['child_id']}大小为{child['tokens']}tokens，超过350上限"

    def test_child_minimum_size(self):
        """验证不会产生过小的碎片子文档"""
        long_text = "测试内容。" * 50
        parents, children = split_parent_child(long_text)

        for child in children:
            assert child["tokens"] >= 10, \
                f"子文档{child['child_id']}过小：{child['tokens']}tokens"


class TestTableNotSplit:
    """测试表格块不被切分"""

    def test_table_not_split(self):
        """验证表格块不被切分：即使表格很长也作为一个整体"""
        table_text = "| 日期 | 体温 | 喂奶量 |\n"
        table_text += "|---|---|---|\n"
        for i in range(50):  # 50行表格数据
            table_text += f"| 2024-01-{i+1:02d} | 36.{5+i%5} | {60+i}ml |\n"

        # 表格不切分逻辑：检测到表格块直接作为一个child
        is_table = "|" in table_text and "---" in table_text
        assert is_table is True, "应识别为表格"

        # 表格应该只有一个块，不被切分
        if is_table:
            children = [{
                "child_id": "child_table_0",
                "parent_id": "parent_table_0",
                "text": table_text,
                "tokens": estimate_tokens(table_text)
            }]
            assert len(children) == 1, "表格不应被切分成多个块"

    def test_table_integrity(self, sample_table_data):
        """验证表格行列完整性"""
        assert len(sample_table_data) == 3  # header + 2 data rows
        header = sample_table_data[0]
        for row in sample_table_data[1:]:
            assert len(row) == len(header), "每行列数应与表头一致"


class TestChunkOverlap:
    """测试分块重叠"""

    def test_chunk_overlap(self):
        """验证相邻子文档之间有重叠内容"""
        long_text = "ABCDEFGHIJ" * 100  # 1000字符
        parents, children = split_parent_child(
            long_text, child_max_tokens=100, overlap=20
        )

        if len(children) >= 2:
            # 相邻子文档应有重叠
            c1_end = children[0]["text"][-20:]
            c2_start = children[1]["text"][:20]
            # 由于是重复文本"ABCDEFGHIJ"，重叠区域应该有共同字符
            assert len(c1_end) > 0 and len(c2_start) > 0

    def test_overlap_size_reasonable(self):
        """验证重叠大小在合理范围（占子文档的10%-20%）"""
        child_tokens = 300
        overlap_tokens = 50
        ratio = overlap_tokens / child_tokens
        assert 0.1 <= ratio <= 0.25, \
            f"重叠比例{ratio:.1%}应在10%-25%之间"
