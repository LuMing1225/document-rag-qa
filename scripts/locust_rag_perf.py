"""
Locust 压测脚本 - RAG 检索性能测试

模拟 100 并发用户，仅测试检索端点（/api/chat/retrieve），不含 LLM 生成。

运行方式:
    locust -f scripts/locust_rag_perf.py \
        --host=http://localhost:8563 \
        --users 100 \
        --spawn-rate 10 \
        --run-time 5m \
        --headless

输出:
    - QPS (每秒请求数)
    - P50/P95/P99 时延
    - 失败率
"""
import random
from locust import HttpUser, task, between, events

# ------------------------------------------------------------------ #
# 测试配置
# ------------------------------------------------------------------ #
# 知识库 ID（需要先运行 init_knowledge_base.py 建库）
KB_ID = "kb_20261001_111326_75ac7c"  # 默认第一个知识库，可根据实际情况修改

# 测试问题集（母婴护理领域典型问题）
TEST_QUESTIONS = [
    "新生儿生理性黄疸怎么办？",
    "宝宝母乳喂养生理性黄疸要停母乳吗？",
    "新生儿光疗需要注意什么？",
    "宝宝溢奶和呛奶有什么区别？",
    "母乳喂养多久添加辅食？",
    "宝宝肠绞痛怎么缓解？",
    "新生儿红臀怎么护理？",
    "宝宝湿疹用什么药膏？",
    "婴儿维生素D每天补多少？",
    "宝宝拍嗝的正确方法是什么？",
    "新生儿胎便多久排完？",
    "宝宝囟门凹陷是脱水吗？",
    "配方奶转奶需要注意什么？",
    "宝宝厌奶期一般持续多久？",
    "婴儿猛长期有什么表现？",
    "宝宝睡眠倒退期怎么办？",
    "新生儿疫苗接种时间表",
    "宝宝体温多少算发烧？",
    "婴儿抚触有什么好处？",
    "宝宝游泳对发育有帮助吗？",
    "新生儿铁剂什么时候开始补？",
    "宝宝补钙需要补多久？",
    "益生菌可以长期吃吗？",
    "宝宝断奶最佳时间是什么时候？",
    "新生儿初乳为什么重要？",
]

# Top-K 切片数量
TOP_K = 5


class RagRetrieveUser(HttpUser):
    """模拟 RAG 检索请求的用户。"""

    # 每个请求间隔 1~3 秒
    wait_time = between(1, 3)

    @task
    def retrieve(self):
        """调用仅检索端点（不含 LLM 生成）。"""
        question = random.choice(TEST_QUESTIONS)
        params = {
            "question": question,
            "kb_id": KB_ID,
            "top_k": TOP_K,
        }
        with self.client.get(
            "/api/chat/retrieve",
            params=params,
            name="/api/chat/retrieve (检索)",
            timeout=30,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    parents = data.get("parents", [])
                    if len(parents) > 0:
                        response.success()
                    else:
                        response.failure("检索返回空结果")
                except Exception as e:
                    response.failure(f"响应解析失败: {e}")
            else:
                response.failure(f"HTTP {response.status_code}")


# ------------------------------------------------------------------ #
# 压测完成后的统计报告
# ------------------------------------------------------------------ #
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """压测结束后打印汇总报告。"""
    stats = environment.stats

    print("\n" + "=" * 70)
    print("  RAG 检索压测报告")
    print("=" * 70)
    print(f"  目标主机: {environment.host}")
    print(f"  并发用户数: {environment.parsed_options.num_users}")
    print(f"  运行时长: {environment.parsed_options.run_time or '手动停止'}")
    print("-" * 70)

    for name, stat in stats.entries.items():
        if name.method == "GET":
            print(f"\n  接口: {name.name}")
            print(f"    总请求数: {stat.num_requests}")
            print(f"    失败数: {stat.num_failures}")
            print(f"    失败率: {stat.num_failures / max(stat.num_requests, 1) * 100:.2f}%")
            print(f"    平均时延: {stat.avg_response_time:.2f} ms")
            print(f"    最小时延: {stat.min_response_time:.2f} ms")
            print(f"    最大时延: {stat.max_response_time:.2f} ms")
            print(f"    P50 时延: {stat.get_response_time_percentile(0.50):.2f} ms")
            print(f"    P95 时延: {stat.get_response_time_percentile(0.95):.2f} ms")
            print(f"    P99 时延: {stat.get_response_time_percentile(0.99):.2f} ms")
            print(f"    QPS (每秒请求数): {stat.total_rps:.2f}")

    print("\n" + "=" * 70)
