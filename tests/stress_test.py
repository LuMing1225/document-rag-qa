"""
千万级向量检索压测脚本
- 生成模拟向量（默认100万，可参数调整到1000万）
- 使用faiss.IndexHNSWFlat支持ANN检索
- 并发检索测试：并发数10/20/50
- 测量P50/P99延迟、QPS
- 目标：延迟≤200ms, QPS≥80

用法:
    python tests/stress_test.py [--n-vectors 1000000] [--dim 1024] [--queries 500]

注意:
    1000万×1024维×4字节 ≈ 40GB内存，本机可能不足
    默认100万向量演示（约4GB内存）
    在更大内存机器上可调整 --n-vectors 10000000 跑千万级
"""
import argparse
import time
import sys
import os
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np


def build_faiss_index(n_vectors=1_000_000, dim=1024, index_type="hnsw"):
    """
    构建FAISS索引
    使用HNSW索引支持千万级ANN检索
    """
    try:
        import faiss
    except ImportError:
        print("错误: 需要安装faiss-cpu: pip install faiss-cpu")
        sys.exit(1)

    print(f"正在生成 {n_vectors:,} 条 {dim} 维随机向量...")
    np.random.seed(42)
    vectors = np.random.randn(n_vectors, dim).astype(np.float32)
    # L2归一化（用于余弦相似度）
    faiss.normalize_L2(vectors)
    print(f"向量生成完成，内存占用约 {n_vectors * dim * 4 / 1024**3:.2f} GB")

    print(f"正在构建 FAISS {index_type} 索引...")
    t0 = time.time()

    if index_type == "hnsw":
        # HNSW索引：M=32, 适合百万到千万级
        index = faiss.IndexHNSWFlat(dim, 32)
        index.hnsw.efConstruction = 64
        index.hnsw.efSearch = 32
    elif index_type == "ivf":
        # IVF索引：nlist=4096
        nlist = min(4096, int(np.sqrt(n_vectors)))
        quantizer = faiss.IndexFlatIP(dim)
        index = faiss.IndexIVFFlat(quantizer, dim, nlist)
        index.train(vectors)
        index.nprobe = 16
    else:
        index = faiss.IndexFlatIP(dim)

    index.add(vectors)
    build_time = time.time() - t0
    print(f"索引构建完成，耗时 {build_time:.1f}s，索引大小: {index.ntotal:,}")

    return index, vectors


def single_query(index, query_vec, top_k=10):
    """单次检索，返回延迟(ms)"""
    t0 = time.perf_counter()
    D, I = index.search(query_vec.reshape(1, -1), top_k)
    latency_ms = (time.perf_counter() - t0) * 1000
    return latency_ms


def concurrent_benchmark(index, n_queries=500, concurrency=10, dim=1024, top_k=10):
    """
    并发检索压测
    返回: (latencies_list, qps)
    """
    np.random.seed(int(time.time()))
    queries = np.random.randn(n_queries, dim).astype(np.float32)
    import faiss
    faiss.normalize_L2(queries)

    latencies = []
    t_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(single_query, index, queries[i], top_k): i
            for i in range(n_queries)
        }
        for future in as_completed(futures):
            lat = future.result()
            latencies.append(lat)

    total_time = time.perf_counter() - t_start
    qps = n_queries / total_time if total_time > 0 else 0

    return latencies, qps


def analyze_latencies(latencies):
    """计算P50/P99等延迟指标"""
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50 = sorted_lat[n // 2]
    p99 = sorted_lat[int(n * 0.99)]
    avg = statistics.mean(sorted_lat)
    return {
        "avg_ms": round(avg, 2),
        "p50_ms": round(p50, 2),
        "p99_ms": round(p99, 2),
        "min_ms": round(min(sorted_lat), 2),
        "max_ms": round(max(sorted_lat), 2),
    }


def main():
    parser = argparse.ArgumentParser(description="FAISS向量检索压测脚本")
    parser.add_argument("--n-vectors", type=int, default=1_000_000,
                        help="向量数量（默认100万，千万级设为10000000）")
    parser.add_argument("--dim", type=int, default=1024, help="向量维度")
    parser.add_argument("--queries", type=int, default=500, help="总查询次数")
    parser.add_argument("--index-type", choices=["hnsw", "ivf", "flat"],
                        default="hnsw", help="FAISS索引类型")
    args = parser.parse_args()

    print("=" * 70)
    print("FAISS 千万级向量检索压测")
    print("=" * 70)
    print(f"向量数量:     {args.n_vectors:,}")
    print(f"向量维度:     {args.dim}")
    print(f"索引类型:     {args.index_type}")
    print(f"总查询数:     {args.queries}")
    mem_gb = args.n_vectors * args.dim * 4 / 1024**3
    print(f"预计内存:     ~{mem_gb:.1f} GB")
    if args.n_vectors >= 10_000_000:
        print("⚠️  千万级向量需要约40GB内存，请确保机器内存充足")
    print("=" * 70)

    # 构建索引
    index, vectors = build_faiss_index(args.n_vectors, args.dim, args.index_type)

    # 预热（首次检索可能慢）
    print("\n预热中...")
    warmup_q = np.random.randn(1, args.dim).astype(np.float32)
    import faiss
    faiss.normalize_L2(warmup_q)
    for _ in range(10):
        single_query(index, warmup_q, top_k=10)

    # 并发测试：10 / 20 / 50
    concurrency_levels = [10, 20, 50]
    report_rows = []

    for conc in concurrency_levels:
        print(f"\n--- 并发数: {conc} ---")
        n_q = min(args.queries, conc * 20)  # 每个并发级别至少跑20轮
        latencies, qps = concurrent_benchmark(
            index, n_queries=n_q, concurrency=conc, dim=args.dim
        )
        stats = analyze_latencies(latencies)
        stats["concurrency"] = conc
        stats["qps"] = round(qps, 1)
        stats["target_latency_ok"] = stats["p99_ms"] <= 200
        stats["target_qps_ok"] = qps >= 80
        report_rows.append(stats)

        print(f"  P50延迟: {stats['p50_ms']} ms")
        print(f"  P99延迟: {stats['p99_ms']} ms  {'✓' if stats['target_latency_ok'] else '✗ (目标≤200ms)'}")
        print(f"  QPS:     {stats['qps']}       {'✓' if stats['target_qps_ok'] else '✗ (目标≥80)'}")

    # 输出汇总表格
    print("\n" + "=" * 70)
    print("压测报告汇总")
    print("=" * 70)
    print(f"{'并发数':>6} | {'P50(ms)':>10} | {'P99(ms)':>10} | {'平均(ms)':>10} | {'QPS':>8} | 达标")
    print("-" * 70)
    for row in report_rows:
        latency_ok = "✓" if row["target_latency_ok"] else "✗"
        qps_ok = "✓" if row["target_qps_ok"] else "✗"
        print(f"{row['concurrency']:>6} | {row['p50_ms']:>10.1f} | {row['p99_ms']:>10.1f} | "
              f"{row['avg_ms']:>10.1f} | {row['qps']:>8.1f} | 延迟{latency_ok} QPS{qps_ok}")
    print("=" * 70)
    print(f"\n目标: P99延迟≤200ms, QPS≥80")
    print(f"索引类型: {args.index_type}, 向量规模: {args.n_vectors:,}")
    if args.n_vectors >= 10_000_000:
        print("注: 千万级测试在高内存机器上运行，本机默认100万演示规模")


if __name__ == "__main__":
    main()
