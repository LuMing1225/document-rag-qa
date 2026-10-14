"""
pytest 共享配置和fixture
"""
import os
import sys
import tempfile
import pytest

# 将项目根目录加入Python路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 测试PDF路径
TEST_PDF_PATH = r"E:\shixunXM\工单4\素材\3长文本\test_pdf\母婴护理科学喂养与疾病预案指南.pdf"


@pytest.fixture
def test_pdf_path():
    """返回测试PDF路径"""
    return TEST_PDF_PATH


@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def sample_text_blocks_double_column():
    """模拟双栏排版的文本块数据（左栏+右栏）"""
    return [
        {"bbox": [72, 100, 250, 120], "text": "左栏标题", "font_size": 16, "top": 100, "x0": 72},
        {"bbox": [72, 130, 250, 150], "text": "左栏正文第一段", "font_size": 11, "top": 130, "x0": 72},
        {"bbox": [72, 160, 250, 180], "text": "左栏正文第二段", "font_size": 11, "top": 160, "x0": 72},
        {"bbox": [300, 100, 480, 120], "text": "右栏标题", "font_size": 16, "top": 100, "x0": 300},
        {"bbox": [300, 130, 480, 150], "text": "右栏正文第一段", "font_size": 11, "top": 130, "x0": 300},
        {"bbox": [300, 160, 480, 180], "text": "右栏正文第二段", "font_size": 11, "top": 160, "x0": 300},
    ]


@pytest.fixture
def sample_text_blocks_single_column():
    """模拟单栏排版的文本块数据"""
    return [
        {"bbox": [72, 100, 480, 120], "text": "章节标题", "font_size": 16, "top": 100, "x0": 72},
        {"bbox": [72, 130, 480, 150], "text": "正文第一段", "font_size": 11, "top": 130, "x0": 72},
        {"bbox": [72, 160, 480, 180], "text": "正文第二段", "font_size": 11, "top": 160, "x0": 72},
    ]


@pytest.fixture
def sample_table_data():
    """模拟表格数据"""
    return [
        ["月龄", "每日次数", "单次奶量(ml)"],
        ["0-1周", "8-12次", "10-30"],
        ["1-4周", "8-10次", "30-90"],
    ]
