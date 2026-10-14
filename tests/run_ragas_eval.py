"""
Ragas评估脚本（简化版）
加载50个母婴护理问答对，调用系统API获取回答，
基于关键词匹配计算Context Recall和Context Precision。

目标：Context Recall >= 90%, Context Precision >= 88%

用法:
    python tests/run_ragas_eval.py [--api-url http://localhost:8563] [--limit 50]
"""
import json
import os
import sys
import time
import argparse
import requests
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
QA_FILE = PROJECT_ROOT / "tests" / "maternal_care_qa_50.json"


def load_qa_pairs():
    """加载50问答对"""
    with open(QA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def call_query_api(question, api_url="http://localhost:8563", kb_name="母婴护理知识库"):
    """调用系统问答API"""
    try:
        resp = requests.post(
            f"{api_url}/api/query",
            json={
                "question": question,
                "kb_name": kb_name,
                "top_k": 5
            },
            timeout=60
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "answer": data.get("answer", ""),
                "sources": data.get("sources", []),
                "retrieval_time_ms": data.get("retrieval_time_ms", 0),
                "generation_time_ms": data.get("generation_time_ms", 0)
            }
        else:
            return {"answer": f"[API错误 {resp.status_code}]", "sources": []}
    except requests.ConnectionError:
        return {"answer": "[连接失败 - 后端未启动]", "sources": []}
    except Exception as e:
        return {"answer": f"[异常: {e}]", "sources": []}


def calculate_keyword_recall(answer, expected_keywords):
    """
    简化版Context Recall：
    标准答案中的关键词有多少比例出现在生成回答中
    """
    if not expected_keywords:
        return 1.0
    answer_lower = answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return hits / len(expected_keywords)


def calculate_keyword_precision(answer, expected_answer):
    """
    简化版Context Precision：
    生成回答中与标准答案重叠的关键词比例
    （用标准答案的关键词在回答中的覆盖率近似）
    """
    if not expected_answer:
        return 1.0
    # 提取标准答案中的关键短语（简单按标点和空格分词）
    expected_words = set()
    for sep in ["，", "。", "；", "：", "、", " ", "（", "）", "(", ")"]:
        expected_answer = expected_answer.replace(sep, "|")
    for word in expected_answer.split("|"):
        word = word.strip()
        if len(word) >= 2:
            expected_words.add(word)

    if not expected_words:
        return 1.0

    answer_lower = answer.lower()
    hits = sum(1 for w in expected_words if w.lower() in answer_lower)
    return hits / len(expected_words)


def run_eval(api_url="http://localhost:8563", limit=50, kb_name="母婴护理知识库"):
    """运行完整评估"""
    qa_pairs = load_qa_pairs()[:limit]
    print(f"加载了 {len(qa_pairs)} 个问答对")
    print(f"API地址: {api_url}")
    print(f"知识库: {kb_name}")
    print("=" * 60)

    results = []
    recall_scores = []
    precision_scores = []
    retrieval_times = []
    generation_times = []

    for i, qa in enumerate(qa_pairs):
        qid = qa["id"]
        question = qa["question"]
        expected = qa["answer"]
        keywords = qa.get("keywords", [])

        print(f"[{i+1}/{len(qa_pairs)}] Q: {question[:40]}...")

        result = call_query_api(question, api_url, kb_name)
        answer = result["answer"]

        recall = calculate_keyword_recall(answer, keywords)
        precision = calculate_keyword_precision(answer, expected)

        recall_scores.append(recall)
        precision_scores.append(precision)
        retrieval_times.append(result.get("retrieval_time_ms", 0))
        generation_times.append(result.get("generation_time_ms", 0))

        results.append({
            "id": qid,
            "question": question,
            "expected_answer": expected,
            "generated_answer": answer,
            "expected_keywords": keywords,
            "context_recall": round(recall, 4),
            "context_precision": round(precision, 4),
            "retrieval_time_ms": result.get("retrieval_time_ms", 0),
        })

        print(f"    Recall={recall:.1%}  Precision={precision:.1%}")

    # 汇总统计
    avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0
    avg_precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0
    avg_retrieval = sum(t for t in retrieval_times if t > 0) / max(1, len([t for t in retrieval_times if t > 0]))

    report = {
        "eval_config": {
            "api_url": api_url,
            "kb_name": kb_name,
            "total_questions": len(qa_pairs),
            "eval_method": "keyword_based_simplified"
        },
        "metrics": {
            "context_recall_avg": round(avg_recall, 4),
            "context_precision_avg": round(avg_precision, 4),
            "recall_target_90pct": avg_recall >= 0.90,
            "precision_target_88pct": avg_precision >= 0.88,
            "avg_retrieval_time_ms": round(avg_retrieval, 1)
        },
        "per_question": results
    }

    # 输出报告
    print("\n" + "=" * 60)
    print("评估报告汇总")
    print("=" * 60)
    print(f"Context Recall (平均):    {avg_recall:.2%}  目标≥90%  {'✓ 达标' if avg_recall >= 0.90 else '✗ 未达标'}")
    print(f"Context Precision (平均):  {avg_precision:.2%}  目标≥88%  {'✓ 达标' if avg_precision >= 0.88 else '✗ 未达标'}")
    print(f"平均检索延迟:              {avg_retrieval:.0f} ms")

    # 保存JSON报告
    report_path = PROJECT_ROOT / "tests" / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存: {report_path}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG系统评估脚本（简化版）")
    parser.add_argument("--api-url", default="http://localhost:8563", help="后端API地址")
    parser.add_argument("--limit", type=int, default=50, help="评估题目数量")
    parser.add_argument("--kb", default="母婴护理知识库", help="知识库名称")
    args = parser.parse_args()

    run_eval(api_url=args.api_url, limit=args.limit, kb_name=args.kb)
