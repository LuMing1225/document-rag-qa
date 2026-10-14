# -*- coding: utf-8 -*-
"""端到端验证：模拟前端完整流程"""
import sys, requests, json
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8563"
PDF = r"E:\shixunXM\工单4\素材\3长文本\test_pdf\母婴护理科学喂养与疾病预案指南.pdf"

print("=" * 60)
print("STEP 1: 上传并解析 PDF")
print("=" * 60)
with open(PDF, "rb") as f:
    r = requests.post(f"{BASE}/api/parse/upload", files={"file": f}, timeout=60)
upload = r.json()
doc_id = upload["doc_id"]
print(f"  doc_id: {doc_id}")
print(f"  pages: {upload['total_pages']}, chunks: {upload['chunk_count']}, tables: {upload['table_count']}")

print()
print("=" * 60)
print("STEP 2: 获取完整解析结果（前端展示用）")
print("=" * 60)
r = requests.get(f"{BASE}/api/parse/{doc_id}", timeout=30)
result = r.json()
chunks = result.get("chunks", [])
tables = result.get("tables", [])
regions = result.get("layout_regions", [])
print(f"  chunks: {len(chunks)} {'✓' if chunks else '✗'}")
print(f"  tables: {len(tables)} {'✓' if tables else '✗'}")
print(f"  layout_regions: {len(regions)} {'✓' if regions else '✗'}")

# 双栏检测
two_col_pages = set()
for rg in regions:
    col = str(rg.get("column", "")).lower()
    if col in ("left", "right"):
        two_col_pages.add(str(rg.get("page_number", "?")))
print(f"  double-column pages: {sorted(two_col_pages)} {'✓' if two_col_pages else '✗'}")

# 表格 Markdown
if tables:
    print(f"  table 1 markdown preview: {tables[0].get('markdown', '')[:80]}...")

# 文本块
text_chunks = [c for c in chunks if c.get("text", "").strip()]
print(f"  non-empty text chunks: {len(text_chunks)} {'✓' if text_chunks else '✗'}")

print()
print("=" * 60)
print("STEP 3: 创建知识库 + 构建索引")
print("=" * 60)
r = requests.post(f"{BASE}/api/knowledge/create", json={"name": "E2E验证库", "description": "端到端测试"}, timeout=30)
kb = r.json()
kb_id = kb["kb_id"]
print(f"  kb_id: {kb_id}")

r = requests.post(f"{BASE}/api/knowledge/{kb_id}/index", json={"doc_id": doc_id}, timeout=180)
idx = r.json()
print(f"  indexed docs: {idx.get('doc_count', 0)}")
print(f"  parents: {idx.get('parent_count', 0)}, children: {idx.get('child_count', 0)}")
print(f"  total_parents: {idx.get('total_parents', 0)}, total_children: {idx.get('total_children', 0)}")
ok_idx = idx.get('total_children', 0) > 0
print(f"  index build: {'✓' if ok_idx else '✗'}")

print()
print("=" * 60)
print("STEP 4: 检索验证")
print("=" * 60)
r = requests.get(f"{BASE}/api/chat/retrieve", params={
    "question": "婴儿黄疸达到多少数值需要采取光疗",
    "kb_id": kb_id, "top_k": 5, "use_reranker": "false"
}, timeout=60)
retr = r.json()
parents = retr.get("parents", [])
print(f"  retrieved parents: {len(parents)} {'✓' if parents else '✗'}")
if parents:
    print(f"  top1 score: {parents[0].get('score')}, pages: {parents[0].get('page_numbers')}")
    print(f"  top1 text preview: {parents[0].get('text', '')[:100]}...")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
all_ok = all([len(chunks) > 0, len(tables) > 0, len(regions) > 0,
               len(two_col_pages) > 0, ok_idx, len(parents) > 0])
print(f"  文本块: {'✓' if chunks else '✗'}")
print(f"  表格: {'✓' if tables else '✗'}")
print(f"  版面区域: {'✓' if regions else '✗'}")
print(f"  双栏检测: {'✓' if two_col_pages else '✗'}")
print(f"  索引构建: {'✓' if ok_idx else '✗'}")
print(f"  检索上下文: {'✓' if parents else '✗'}")
print(f"  总体: {'✓ ALL PASS' if all_ok else '✗ SOME FAILED'}")
