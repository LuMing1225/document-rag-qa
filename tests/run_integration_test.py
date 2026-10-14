"""
集成测试脚本：验证完整RAG流程
1. 上传PDF解析
2. 创建知识库
3. 构建索引
4. 检索测试
5. 问答测试
"""
import requests
import json
import time
import sys

BASE = "http://localhost:8563"
PDF_PATH = r"E:\shixunXM\工单4\素材\3长文本\test_pdf\母婴护理科学喂养与疾病预案指南.pdf"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def test_health():
    log("=== 1. 健康检查 ===")
    r = requests.get(f"{BASE}/health", timeout=10)
    data = r.json()
    log(f"状态: {data['status']}, 服务: {data['service']}, 端口: {data['backend_port']}")
    assert data["status"] == "ok"
    return True

def test_upload_parse():
    log("\n=== 2. 上传PDF并解析 ===")
    with open(PDF_PATH, "rb") as f:
        files = {"file": ("母婴护理指南.pdf", f, "application/pdf")}
        r = requests.post(f"{BASE}/api/parse/upload", files=files, timeout=120)
    data = r.json()
    log(f"解析结果: doc_id={data.get('doc_id')}, 页数={data.get('total_pages')}, 块数={data.get('chunk_count')}, 区域数={data.get('region_count')}, 表格数={data.get('table_count')}, 状态={data.get('status')}")

    # 区域类型分布
    region_types = data.get("region_types", {})
    if region_types:
        log(f"区域类型分布: {region_types}")

    # 通过GET获取详细解析结果，验证表格块和标题块
    doc_id = data.get("doc_id")
    r2 = requests.get(f"{BASE}/api/parse/{doc_id}", timeout=10)
    detail = r2.json()
    table_chunks = [c for c in detail.get("chunks", []) if c.get("layout_type") == "table"]
    title_chunks = [c for c in detail.get("chunks", []) if c.get("layout_type") == "title"]
    log(f"详细解析: 表格块={len(table_chunks)}, 标题块={len(title_chunks)}")
    for t in table_chunks:
        log(f"  表格: 第{t['page_number']}页, {t['text'][:60]}...")
    
    doc_id = data.get("doc_id")
    assert doc_id, "doc_id为空"
    assert data.get("total_pages") == 2, "页数应为2"
    return doc_id

def test_create_kb():
    log("\n=== 3. 创建知识库 ===")
    r = requests.post(f"{BASE}/api/knowledge/create", json={
        "name": "母婴护理知识库",
        "description": "科学喂养与疾病预案指南"
    }, timeout=10)
    data = r.json()
    kb_id = data.get("kb_id")
    log(f"知识库创建: kb_id={kb_id}, 名称={data.get('name')}")
    assert kb_id
    return kb_id

def test_build_index(kb_id, doc_id):
    log("\n=== 4. 构建父子分块+向量索引 ===")
    r = requests.post(f"{BASE}/api/knowledge/{kb_id}/index", json={
        "doc_id": doc_id
    }, timeout=180)
    data = r.json()
    log(f"索引构建: 父文档={data.get('parent_count')}, 子文档={data.get('child_count')}, 向量数={data.get('vector_count')}, 耗时={data.get('build_time')}s")
    assert data.get("child_count", 0) > 0, "子文档数应为正"
    return data

def test_chunks_view(kb_id):
    log("\n=== 5. 查看父子分块结构 ===")
    r = requests.get(f"{BASE}/api/knowledge/{kb_id}/chunks?page=1&page_size=10", timeout=10)
    data = r.json()
    log(f"分块总数: {data.get('total')}")
    for p in data.get("parents", [])[:3]:
        log(f"  父文档 {p['parent_id']}: {len(p.get('text',''))}字, {len(p.get('child_ids',[]))}个子块, 页码={p.get('page_numbers')}")
    return True

def test_retrieve(kb_id):
    log("\n=== 6. 混合检索测试（多向量评分） ===")
    questions = [
        "婴儿光疗期间如何护理眼睛？",
        "新生儿母乳喂养有什么好处？",
        "婴幼儿疫苗接种时间表是什么？",
    ]
    for q in questions:
        r = requests.get(f"{BASE}/api/chat/retrieve", params={
            "question": q,
            "kb_id": kb_id,
            "top_k": 3
        }, timeout=60)
        data = r.json()
        parents = data.get("parents", data.get("retrieved_parents", []))
        log(f"\n问题: {q}")
        log(f"  召回父文档数: {len(parents)}")
        for p in parents[:2]:
            log(f"  - {p.get('parent_id','?')}: 综合分={p.get('score',0):.4f}, 稠密分={p.get('dense_score',0):.4f}, 重排分={p.get('rerank_score',0):.4f}, 页={p.get('page_numbers')}")
            log(f"    预览: {p.get('text','')[:80]}...")
    return True

def test_qa(kb_id):
    log("\n=== 7. RAG问答测试 ===")
    question = "新生儿光疗期间需要注意哪些护理要点？"
    log(f"问题: {question}")
    r = requests.post(f"{BASE}/api/chat/query", json={
        "question": question,
        "kb_id": kb_id,
        "top_k": 3
    }, timeout=120)
    data = r.json()
    log(f"回答: {data.get('answer','')[:300]}")
    log(f"响应时间: {data.get('response_time')}s, 模型: {data.get('model_used')}")
    log(f"检索上下文数: {len(data.get('retrieved_parents', data.get('parents', [])))}")
    assert data.get("answer"), "回答为空"
    return True

if __name__ == "__main__":
    try:
        test_health()
        doc_id = test_upload_parse()
        kb_id = test_create_kb()
        test_build_index(kb_id, doc_id)
        test_chunks_view(kb_id)
        test_retrieve(kb_id)
        test_qa(kb_id)
        log("\n" + "="*60)
        log("全部集成测试通过！")
        log("="*60)
    except Exception as e:
        log(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
