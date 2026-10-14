"""
批量初始化知识库脚本

流程：
1. 创建知识库
2. 上传母婴护理指南 PDF -> 解析 -> 建索引
3. 从工单3专利库随机选 20+ 篇 PDF -> 逐篇上传解析建索引
4. 输出导入统计

使用前请确保：
- 后端服务已启动 (localhost:8563)
- Milvus 已启动 (localhost:19530)
- Ollama 运行中 (bge-m3:latest 已加载)
"""
import json
import random
import sys
import time
from pathlib import Path
from typing import List

import requests

# ------------------------------------------------------------------ #
# 配置
# ------------------------------------------------------------------ #
BACKEND_URL = "http://localhost:8563"

# 母婴护理指南 PDF
MATERNAL_GUIDE_PDF = r"E:\shixunXM\工单4\素材\3长文本\test_pdf\母婴护理科学喂养与疾病预案指南.pdf"

# 专利 PDF 目录
PATENT_PDF_DIR = r"E:\shixunXM\工单3\工单3附件\14-17附件\original_problems\documents"

# 随机选取的专利数量
PATENT_COUNT = 25


def create_kb(name: str, description: str = "") -> str:
    """创建知识库，返回 kb_id。"""
    resp = requests.post(
        f"{BACKEND_URL}/api/knowledge/create",
        json={"name": name, "description": description},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    kb_id = data["kb_id"]
    print(f"[OK] 创建知识库: {name} -> {kb_id}")
    return kb_id


def upload_and_parse_pdf(pdf_path: str) -> str:
    """上传 PDF 并完成解析，返回 doc_id。"""
    filename = Path(pdf_path).name
    with open(pdf_path, "rb") as f:
        files = {"file": (filename, f, "application/pdf")}
        resp = requests.post(
            f"{BACKEND_URL}/api/parse/upload",
            files=files,
            timeout=300,  # PDF 解析可能较慢
        )
    resp.raise_for_status()
    data = resp.json()
    doc_id = data["doc_id"]
    print(f"  [解析完成] {filename}: {data['total_pages']}页, {data['chunk_count']}块, 耗时{data['parse_time']:.1f}s")
    return doc_id


def build_index(kb_id: str, doc_id: str) -> dict:
    """对已解析文档构建父子分块 + 向量索引。"""
    resp = requests.post(
        f"{BACKEND_URL}/api/knowledge/{kb_id}/index",
        json={"doc_id": doc_id},
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"  [建索引] 父块={data['parent_count']}, 子块={data['child_count']}, "
          f"知识库总计: 父={data['total_parents']}, 子={data['total_children']}")
    return data


def get_kb_stats(kb_id: str) -> dict:
    """获取知识库统计信息。"""
    resp = requests.get(f"{BACKEND_URL}/api/knowledge/list", timeout=30)
    resp.raise_for_status()
    kbs = resp.json()
    for kb in kbs:
        if kb["kb_id"] == kb_id:
            return kb
    return {}


def main():
    print("=" * 60)
    print("  批量初始化知识库")
    print("=" * 60)

    # 检查后端是否可用
    try:
        resp = requests.get(f"{BACKEND_URL}/docs", timeout=5)
        if resp.status_code != 200:
            raise ConnectionError
    except Exception:
        print(f"[错误] 后端服务 {BACKEND_URL} 不可用，请先启动后端！")
        sys.exit(1)
    print(f"[OK] 后端服务可用: {BACKEND_URL}")

    # Step 1: 创建知识库
    print("\n[Step 1] 创建知识库...")
    kb_id = create_kb(
        name="母婴护理+专利综合知识库",
        description="包含母婴护理科学喂养指南 + 25篇专利文献的综合知识库",
    )

    # Step 2: 导入母婴护理指南
    print(f"\n[Step 2] 导入母婴护理指南 PDF...")
    if Path(MATERNAL_GUIDE_PDF).exists():
        try:
            doc_id = upload_and_parse_pdf(MATERNAL_GUIDE_PDF)
            build_index(kb_id, doc_id)
            print(f"  [完成] 母婴护理指南已导入")
        except Exception as e:
            print(f"  [失败] 母婴护理指南导入失败: {e}")
    else:
        print(f"  [跳过] 文件不存在: {MATERNAL_GUIDE_PDF}")

    # Step 3: 随机选取专利 PDF 并导入
    print(f"\n[Step 3] 从专利库随机选取 {PATENT_COUNT} 篇 PDF 导入...")
    patent_dir = Path(PATENT_PDF_DIR)
    if not patent_dir.exists():
        print(f"  [警告] 专利目录不存在: {patent_dir}")
    else:
        all_pdfs = list(patent_dir.glob("*.pdf"))
        print(f"  专利库共 {len(all_pdfs)} 篇 PDF")

        # 随机选取
        selected = random.sample(all_pdfs, min(PATENT_COUNT, len(all_pdfs)))
        print(f"  随机选取 {len(selected)} 篇:")
        for i, p in enumerate(selected, 1):
            print(f"    {i}. {p.name}")

        # 逐篇导入
        success_count = 0
        fail_count = 0
        for i, pdf_path in enumerate(selected, 1):
            print(f"\n  [{i}/{len(selected)}] 导入: {pdf_path.name}")
            try:
                doc_id = upload_and_parse_pdf(str(pdf_path))
                build_index(kb_id, doc_id)
                success_count += 1
            except Exception as e:
                print(f"  [失败] {pdf_path.name}: {e}")
                fail_count += 1
                continue

    # Step 4: 输出最终统计
    print("\n" + "=" * 60)
    print("  导入完成 - 统计信息")
    print("=" * 60)
    stats = get_kb_stats(kb_id)
    if stats:
        print(f"  知识库名称: {stats.get('name', '')}")
        print(f"  知识库 ID: {kb_id}")
        print(f"  文档数量: {stats.get('document_count', 0)}")
        print(f"  父块数量: {stats.get('parent_count', 0)}")
        print(f"  子块数量: {stats.get('child_count', 0)}")
    else:
        print(f"  知识库 ID: {kb_id}")

    print("\n  测试检索示例:")
    print(f"  curl \"http://localhost:8563/api/chat/retrieve?question=新生儿黄疸怎么办&kb_id={kb_id}&top_k=3\"")
    print("=" * 60)


if __name__ == "__main__":
    main()
