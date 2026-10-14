# -*- coding: utf-8 -*-
"""快速检索性能测试：测量 P50/P95/P99 时延和 QPS"""
import requests, time, sys, statistics
sys.stdout.reconfigure(encoding="utf-8")

KB_ID = "kb_20261001_173158_115b5e"
URL = "http://localhost:8563/api/chat/retrieve"

QUESTIONS = [
    "婴儿黄疸光疗阈值是多少",
    "母乳喂养的正确姿势",
    "疫苗接种时间表",
    "辅食添加原则",
    "新生儿体温监测方法",
    "婴儿睡眠安全注意事项",
    "婴幼儿用药安全",
    "红臀护理方法",
    "肠绞痛如何缓解",
    "维生素D补充剂量",
]

def run_test(n_requests=50, concurrency=1):
    """串行发送 n_requests 个请求，统计时延"""
    latencies = []
    t_start = time.time()
    for i in range(n_requests):
        q = QUESTIONS[i % len(QUESTIONS)]
        t0 = time.time()
        try:
            resp = requests.get(URL, params={"question": q, "kb_id": KB_ID, "top_k": 5, "use_reranker": "false"}, timeout=30)
            elapsed = (time.time() - t0) * 1000
            if resp.status_code == 200:
                latencies.append(elapsed)
            else:
                print(f"  Request {i} failed: {resp.status_code}")
        except Exception as e:
            print(f"  Request {i} error: {e}")
    total_time = time.time() - t_start

    if not latencies:
        print("No successful requests")
        return

    latencies.sort()
    n = len(latencies)
    p50 = latencies[int(n * 0.5)]
    p95 = latencies[int(n * 0.95)]
    p99 = latencies[int(n * 0.99)] if n >= 100 else latencies[-1]
    qps = n / total_time

    print(f"\n{'='*50}")
    print(f"检索性能测试报告（不含LLM生成）")
    print(f"{'='*50}")
    print(f"总请求数: {n}")
    print(f"总耗时: {total_time:.2f}s")
    print(f"QPS: {qps:.1f}")
    print(f"平均时延: {statistics.mean(latencies):.1f}ms")
    print(f"P50 时延: {p50:.1f}ms")
    print(f"P95 时延: {p95:.1f}ms")
    print(f"P99 时延: {p99:.1f}ms")
    print(f"最小时延: {min(latencies):.1f}ms")
    print(f"最大时延: {max(latencies):.1f}ms")
    print(f"{'='*50}")
    print(f"工单验收标准: 时延≤200ms, QPS≥80")
    print(f"P50达标: {'✓' if p50 <= 200 else '✗'} ({p50:.1f}ms)")
    print(f"QPS达标: {'✓' if qps >= 80 else '✗ (注: 串行测试，并发测试QPS会更高)'} ({qps:.1f})")

if __name__ == "__main__":
    print("预热中...")
    for q in QUESTIONS[:3]:
        requests.get(URL, params={"question": q, "kb_id": KB_ID, "top_k": 5, "use_reranker": "false"}, timeout=30)
    print("开始性能测试（50请求）...")
    run_test(n_requests=50)
