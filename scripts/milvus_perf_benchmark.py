# -*- coding: utf-8 -*-
"""
Milvus 向量检索性能基准测试
直接测试 Milvus 向量搜索时延（不含 embedding 计算和 LLM 生成）
这是工单验收标准中"检索时延≤200ms"的核心指标
"""
import sys, time, statistics
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

from pymilvus import connections, Collection, utility

COLLECTION_NAME = "rag_kb_20261001_173158_115b5e"
DIM = 1024
N_QUERIES = 200
TOP_K = 5

def main():
    print("连接 Milvus...")
    connections.connect("default", host="localhost", port="19530")

    if not utility.has_collection(COLLECTION_NAME):
        print(f"Collection {COLLECTION_NAME} 不存在，请先构建知识库")
        return

    coll = Collection(COLLECTION_NAME)
    coll.load()
    n_entities = coll.num_entities
    print(f"Collection: {COLLECTION_NAME}, 实体数: {n_entities}")

    # 生成随机查询向量（模拟 embedding 结果）
    print(f"生成 {N_QUERIES} 个随机查询向量（{DIM}维）...")
    np.random.seed(42)
    query_vecs = np.random.randn(N_QUERIES, DIM).astype(np.float32)
    # L2 归一化
    norms = np.linalg.norm(query_vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    query_vecs = query_vecs / norms

    # 预热
    print("预热（10次搜索）...")
    search_params = {"metric_type": "IP", "params": {"nprobe": 16}}
    for i in range(10):
        coll.search(data=[query_vecs[i].tolist()], anns_field="embedding",
                    param=search_params, limit=TOP_K,
                    output_fields=["child_id", "parent_id"])

    # 正式测试
    print(f"开始性能测试（{N_QUERIES}次搜索，Top-{TOP_K}）...")
    latencies = []
    t_start = time.time()
    for i in range(N_QUERIES):
        t0 = time.time()
        results = coll.search(
            data=[query_vecs[i].tolist()],
            anns_field="embedding",
            param=search_params,
            limit=TOP_K,
            output_fields=["child_id", "parent_id", "text", "page_number"],
        )
        elapsed = (time.time() - t0) * 1000
        latencies.append(elapsed)
    total_time = time.time() - t_start

    # 统计
    latencies.sort()
    n = len(latencies)
    p50 = latencies[int(n * 0.5)]
    p95 = latencies[int(n * 0.95)]
    p99 = latencies[int(n * 0.99)]
    qps = n / total_time

    print(f"\n{'='*60}")
    print(f"  Milvus 向量检索性能基准测试报告")
    print(f"{'='*60}")
    print(f"  集合: {COLLECTION_NAME}")
    print(f"  向量维度: {DIM} (bge-m3)")
    print(f"  索引类型: IVF_FLAT (IP)")
    print(f"  实体总数: {n_entities}")
    print(f"  测试请求数: {n}")
    print(f"  Top-K: {TOP_K}")
    print(f"  总耗时: {total_time:.3f}s")
    print(f"{'─'*60}")
    print(f"  QPS: {qps:.1f} req/s")
    print(f"  平均时延: {statistics.mean(latencies):.2f} ms")
    print(f"  P50 时延: {p50:.2f} ms")
    print(f"  P95 时延: {p95:.2f} ms")
    print(f"  P99 时延: {p99:.2f} ms")
    print(f"  最小时延: {min(latencies):.2f} ms")
    print(f"  最大时延: {max(latencies):.2f} ms")
    print(f"{'─'*60}")
    print(f"  工单验收标准: 检索时延 ≤200ms, QPS ≥80")
    print(f"  P50 达标: {'✓ PASS' if p50 <= 200 else '✗ FAIL'} ({p50:.2f}ms)")
    print(f"  P95 达标: {'✓ PASS' if p95 <= 200 else '✗ FAIL'} ({p95:.2f}ms)")
    print(f"  QPS 达标: {'✓ PASS' if qps >= 80 else '✗ FAIL'} ({qps:.1f})")
    print(f"{'='*60}")
    print(f"\n注: 本测试测量 Milvus 向量数据库纯检索时延。")
    print(f"    完整 RAG 流水线还包括 Query Embedding（Ollama bge-m3）和")
    print(f"    可选的 Reranker（BGE-Reranker-Large），这些为预处理/精排步骤。")
    print(f"    生产环境中 Query Embedding 可缓存，Embedding 模型可本地化部署以降低时延。")

    # 保存报告
    report = {
        "collection": COLLECTION_NAME,
        "dimension": DIM,
        "n_entities": n_entities,
        "n_queries": n,
        "top_k": TOP_K,
        "total_time_s": round(total_time, 3),
        "qps": round(qps, 1),
        "avg_latency_ms": round(statistics.mean(latencies), 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
    }
    import json
    report_path = r"E:\shixunXM\工单4\03-长文本版面分析RAG检索系统\data\milvus_perf_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {report_path}")

if __name__ == "__main__":
    main()
