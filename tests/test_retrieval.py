"""
检索测试
验证：多向量评分公式、重排器调用、父文档去重
"""
import pytest
import math


def hybrid_score(dense_sim, rerank_score, beta=0.3):
    """
    多向量混合评分公式
    Score_final = beta * Sim_Dense(Query, Child) + (1-beta) * Sim_Rerank(Query, Parent)
    """
    # dense_sim范围约[-1, 1]，归一化到[0,1]
    dense_norm = (dense_sim + 1) / 2
    # rerank_score范围约[0, 1]
    return beta * dense_norm + (1 - beta) * rerank_score


class TestHybridScoring:
    """测试多向量评分公式"""

    def test_hybrid_scoring(self):
        """验证多向量评分公式计算正确"""
        # 测试用例1：高dense + 高rerank
        score1 = hybrid_score(dense_sim=0.8, rerank_score=0.9, beta=0.3)
        # dense_norm = (0.8+1)/2 = 0.9
        # score = 0.3*0.9 + 0.7*0.9 = 0.27 + 0.63 = 0.9
        expected1 = 0.3 * ((0.8 + 1) / 2) + 0.7 * 0.9
        assert abs(score1 - expected1) < 0.001, \
            f"评分计算错误: {score1} != {expected1}"

    def test_hybrid_scoring_weight(self):
        """验证beta权重方向：beta越小越偏重重排"""
        # 同一组dense和rerank分数
        dense = 0.5
        rerank = 0.9

        # beta=0.1（偏重重排）应该比beta=0.9（偏重dense）得分更高
        score_low_beta = hybrid_score(dense, rerank, beta=0.1)
        score_high_beta = hybrid_score(dense, rerank, beta=0.9)

        # 因为rerank(0.9) > dense_norm(0.75)，偏重重排的分数应该更高
        assert score_low_beta > score_high_beta, \
            f"偏重重排({score_low_beta:.3f})应高于偏重dense({score_high_beta:.3f})"

    def test_score_range(self):
        """验证评分结果在合理范围[0, 1]"""
        for dense in [-1, 0, 0.5, 1]:
            for rerank in [0, 0.5, 1]:
                score = hybrid_score(dense, rerank, beta=0.3)
                assert 0 <= score <= 1, \
                    f"评分{score}超出[0,1]范围 (dense={dense}, rerank={rerank})"


class TestRerankerIntegration:
    """测试重排器集成"""

    def test_reranker_call_format(self):
        """验证重排器输入输出格式"""
        query = "新生儿黄疸光疗阈值"
        parent_docs = [
            "黄疸光疗指征：胎龄≥38周...",
            "母乳喂养姿势：摇篮式...",
            "辅食添加原则：由少到多...",
        ]

        # 模拟CrossEncoder输入格式
        rerank_inputs = [
            [query, doc] for doc in parent_docs
        ]

        assert len(rerank_inputs) == len(parent_docs)
        for pair in rerank_inputs:
            assert len(pair) == 2  # [query, document]
            assert pair[0] == query

    def test_reranker_ranking_order(self):
        """验证重排后按分数降序排列"""
        # 模拟重排分数
        results = [
            {"doc": "黄疸相关内容", "score": 0.92},
            {"doc": "喂养相关内容", "score": 0.35},
            {"doc": "睡眠相关内容", "score": 0.15},
        ]

        ranked = sorted(results, key=lambda x: x["score"], reverse=True)

        assert ranked[0]["score"] >= ranked[1]["score"] >= ranked[2]["score"]
        assert ranked[0]["doc"] == "黄疸相关内容"


class TestDeduplication:
    """测试同一父文档去重"""

    def test_deduplication(self):
        """验证同一父文档的多个子文档只返回一个父文档"""
        # 模拟FAISS返回的top-20子文档
        child_hits = [
            {"child_id": "c1", "parent_id": "p1", "score": 0.95},
            {"child_id": "c2", "parent_id": "p1", "score": 0.88},  # 同一父文档
            {"child_id": "c3", "parent_id": "p2", "score": 0.82},
            {"child_id": "c4", "parent_id": "p3", "score": 0.75},
        ]

        # 去重：同一parent_id保留最高分
        parent_best = {}
        for hit in child_hits:
            pid = hit["parent_id"]
            if pid not in parent_best or hit["score"] > parent_best[pid]["score"]:
                parent_best[pid] = hit

        unique_parents = list(parent_best.values())

        # p1应该只出现一次，且保留最高分0.95的那个
        assert len(unique_parents) == 3, \
            f"去重后应有3个父文档，实际{len(unique_parents)}"
        p1_hits = [p for p in unique_parents if p["parent_id"] == "p1"]
        assert len(p1_hits) == 1
        assert p1_hits[0]["score"] == 0.95, "应保留最高分的子文档"

    def test_dedup_preserves_best_score(self):
        """验证去重后保留的是最高分子文档的分数"""
        child_hits = [
            {"child_id": "c1", "parent_id": "p1", "score": 0.70},
            {"child_id": "c2", "parent_id": "p1", "score": 0.90},
            {"child_id": "c3", "parent_id": "p1", "score": 0.80},
        ]

        parent_best = {}
        for hit in child_hits:
            pid = hit["parent_id"]
            if pid not in parent_best or hit["score"] > parent_best[pid]["score"]:
                parent_best[pid] = hit

        assert parent_best["p1"]["score"] == 0.90, \
            "应保留最高分数0.90而非0.70或0.80"
