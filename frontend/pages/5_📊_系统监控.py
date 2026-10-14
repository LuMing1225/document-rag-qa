# -*- coding: utf-8 -*-
"""
页面 5：系统监控
================
- 后端健康状态 /health
- Ollama 连接状态、已加载模型
- 知识库统计：库数量、总文档数、总 chunk 数
- 检索性能：最近查询响应时间
- 系统配置参数展示（β、分块大小、top_k 等）
"""

import sys
from pathlib import Path

import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from utils import get_health, list_kbs, get_kb_stats  # noqa: E402

st.set_page_config(page_title="系统监控", page_icon="📊", layout="wide")

st.markdown("<div class='breadcrumb'>功能 / 系统监控</div>", unsafe_allow_html=True)
st.markdown("<div class='page-title'>📊 系统监控面板</div>", unsafe_allow_html=True)
st.write("查看后端健康状态、模型加载情况、知识库规模与检索性能。")


def pick(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d.get(k)
    return default


if st.button("🔄 刷新状态", type="primary"):
    st.cache_data.clear()

health = get_health()
backend_up = health.get("status") not in (None, "down", "error")

# ---------------------------------------------------------------------------
# 健康状态卡片
# ---------------------------------------------------------------------------
st.markdown("### ❤️ 后端健康状态")
c1, c2, c3 = st.columns(3)
with c1:
    if backend_up:
        st.success("● 后端服务在线")
    else:
        st.error("● 后端服务离线")
with c2:
    ollama = health.get("ollama_status") or health.get("ollama", "unknown")
    if ollama == "ok":
        st.success("● Ollama 就绪")
    elif backend_up:
        st.warning(f"● Ollama 状态：{ollama}")
    else:
        st.error("● Ollama 未连接")
with c3:
    st.metric("API 地址", "http://localhost:8563")

# 已加载模型（兼容 dict 和 list 两种返回格式）
models_raw = health.get("models") or health.get("ollama_models") or {}
st.markdown("#### 🤖 已加载模型")
if isinstance(models_raw, dict) and models_raw:
    for mname, mstate in models_raw.items():
        ok = str(mstate) == "ok"
        (st.success if ok else st.warning)(f"{'✅' if ok else '⚠️'} {mname}：{mstate}")
elif isinstance(models_raw, list) and models_raw:
    for mname in models_raw:
        st.success(f"✅ {mname}")
else:
    st.info("后端未返回已加载模型列表。")

# ---------------------------------------------------------------------------
# 知识库统计
# ---------------------------------------------------------------------------
st.markdown("### 📚 知识库统计")
kbs = list_kbs()
total_docs = 0
total_chunks = 0
for kb in kbs:
    if isinstance(kb, dict):
        total_docs += int(pick(kb, "document_count", "docs_count", default=0) or 0)
        pc = int(pick(kb, "parent_count", default=0) or 0)
        cc = int(pick(kb, "child_count", default=0) or 0)
        total_chunks += pc + cc

k1, k2, k3 = st.columns(3)
k1.metric("知识库数量", len(kbs))
k2.metric("总文档数", total_docs)
k3.metric("总分块数", total_chunks)

if kbs:
    with st.expander("各知识库明细", expanded=False):
        for kb in kbs:
            if isinstance(kb, dict):
                st.write(
                    f"• **{pick(kb,'name',default='?')}**　"
                    f"文档 {pick(kb,'document_count',default='—')}　"
                    f"父块 {pick(kb,'parent_count',default='—')} / 子块 {pick(kb,'child_count',default='—')}　"
                    f"索引 {pick(kb,'indexed',default='—')}"
                )

# 系统级 stats 接口
stats = get_kb_stats()
if stats:
    with st.expander("后端返回的系统统计（原始）", expanded=False):
        st.json(stats)

# ---------------------------------------------------------------------------
# 检索性能
# ---------------------------------------------------------------------------
st.markdown("### ⚡ 检索性能")
rt = pick(stats, "avg_response_time", "response_time", "last_response_time", default=None)
p1, p2, p3 = st.columns(3)
p1.metric("最近响应时间(s)", f"{rt}" if rt is not None else "—")
p2.metric("平均稠密检索", "—")
p3.metric("平均重排耗时", "—")
st.caption("提示：实际响应时间会在「💬 智能问答」每次回答后显示。")

# ---------------------------------------------------------------------------
# 系统配置参数
# ---------------------------------------------------------------------------
st.markdown("### ⚙️ 系统配置参数")
cfg = health.get("config", {}) if isinstance(health.get("config"), dict) else {}
config_rows = {
    "嵌入模型": pick(cfg, "embedding_model", "embed_model", default="bge-m3:latest"),
    "生成模型": pick(cfg, "llm_model", "generator", default="qwen3:8b"),
    "重排器": pick(cfg, "reranker", "rerank_model", default="bge-reranker-large"),
    "稠密权重 β": pick(cfg, "beta", "dense_weight", default=0.4),
    "默认 top_k": pick(cfg, "top_k", "default_top_k", default=5),
    "父分块大小(字)": pick(cfg, "parent_chunk_size", "parent_size", default=1800),
    "子分块大小(字)": pick(cfg, "child_chunk_size", "child_size", default=450),
}
cc1, cc2 = st.columns(2)
items = list(config_rows.items())
for i, (k, v) in enumerate(items):
    (cc1 if i % 2 == 0 else cc2).metric(k, str(v))

if cfg:
    with st.expander("后端返回的配置详情（原始）", expanded=False):
        st.json(cfg)
