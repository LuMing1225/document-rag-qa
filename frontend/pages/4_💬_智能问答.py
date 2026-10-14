# -*- coding: utf-8 -*-
"""
页面 4：智能问答
=================
- 聊天式界面 st.chat_message
- 提问 POST /api/chat/query
- 展示 AI 回答（Markdown）、检索上下文（可折叠）、多向量评分公式
- 回答来源页码标注、示例问题按钮
"""

import sys
from pathlib import Path

import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from utils import list_kbs, query  # noqa: E402

st.set_page_config(page_title="智能问答", page_icon="💬", layout="wide")

st.markdown("<div class='breadcrumb'>功能 / 智能问答</div>", unsafe_allow_html=True)
st.markdown("<div class='page-title'>💬 母婴护理智能问答</div>", unsafe_allow_html=True)
st.write("基于知识库的混合检索（稠密 + 重排）与 LLM 生成，回答带来源溯源。")


def pick(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d.get(k)
    return default


# ---------------------------------------------------------------------------
# 侧边选择：知识库、检索参数
# ---------------------------------------------------------------------------
kbs = list_kbs()
kb_options = {}
for kb in kbs:
    kb_id = pick(kb, "kb_id", "id")
    kb_name = pick(kb, "name", default=str(kb_id))
    if kb_id:
        kb_options[f"{kb_name}（{kb_id}）"] = kb_id

with st.sidebar:
    st.markdown("### 💬 问答设置")
    if kb_options:
        sel_label = st.selectbox("选择知识库", list(kb_options.keys()), key="chat_kb_sel")
        kb_id = kb_options[sel_label]
    else:
        st.warning("暂无知识库")
        kb_id = None
    top_k = st.slider("top_k（最终返回父文档数）", 2, 15, 5)
    beta = st.slider("稠密权重 β（Score=β·稠密+(1-β)·重排）", 0.0, 1.0, 0.4, 0.05)

# 初始化聊天历史
st.session_state.setdefault("chat_history", [])

# ---------------------------------------------------------------------------
# 示例问题
# ---------------------------------------------------------------------------
EXAMPLES = [
    "新生儿脐带护理的正确步骤是什么？",
    "产后产妇出现恶露异常应该如何观察与处理？",
    "母乳不足时如何进行混合喂养？",
    "婴幼儿常见湿疹的护理要点有哪些？",
    "新生儿抚触的操作流程和注意事项？",
]
st.markdown("**试试示例问题：**")
ex_cols = st.columns(len(EXAMPLES))
for col, q in zip(ex_cols, EXAMPLES):
    if col.button(q, use_container_width=True, key=f"ex_{q[:6]}"):
        st.session_state["_pending_q"] = q

# 定义上下文渲染函数（先定义，再在历史消息渲染中调用）
def _render_contexts(contexts, beta):
    for i, ctx in enumerate(contexts, 1):
        if not isinstance(ctx, dict):
            continue
        dense = pick(ctx, "score_dense", "sim_dense", "dense_score", "dense", default=None)
        rerank = pick(ctx, "score_rerank", "sim_rerank", "rerank_score", "rerank", default=None)
        final = pick(ctx, "score", "final_score", "combined_score", default=None)
        page = pick(ctx, "page", "page_no", "pages", default=None)
        if page is None:
            pns = ctx.get("page_numbers")
            page = ",".join(str(x) for x in pns) if isinstance(pns, list) and pns else "—"
        text = pick(ctx, "text", "content", "chunk", default="")
        source = pick(ctx, "source", "filename", "doc_name", default="")

        score_line = f"**#{i}** 来源：{source}　第 {page} 页"
        st.markdown(score_line)
        parts = []
        if dense is not None:
            parts.append(f"稠密分={float(dense):.4f}")
        if rerank is not None:
            parts.append(f"重排分={float(rerank):.4f}")
        if final is not None:
            parts.append(f"综合分={float(final):.4f}")
        if parts:
            st.caption(" ｜ ".join(parts))
        st.write(str(text)[:400])
        st.divider()


# ---------------------------------------------------------------------------
# 渲染历史消息（此时 _render_contexts 已定义）
# ---------------------------------------------------------------------------
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("contexts"):
            with st.expander(f"📚 检索到 {len(msg['contexts'])} 条上下文", expanded=False):
                _render_contexts(msg["contexts"], beta)


# ---------------------------------------------------------------------------
# 输入处理
# ---------------------------------------------------------------------------
def handle_question(question: str):
    if not question.strip():
        return
    if not kb_id:
        st.warning("请先在左侧选择知识库。")
        return
    # 显示用户消息
    st.session_state["chat_history"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("正在检索知识库并生成回答……"):
            resp = query(question, kb_id=kb_id, top_k=top_k, beta=beta)
        if "error" in resp:
            st.error(f"❌ {resp['error']}")
            return
        answer = pick(resp, "answer", "result", "response", default="（无回答内容）")
        contexts = resp.get("contexts") or resp.get("retrieved_parents") or resp.get("sources") or resp.get("chunks") or []
        rt = pick(resp, "response_time", "elapsed", "time", default=None)
        model_used = pick(resp, "model_used", "model", default="")

        st.markdown(answer)
        # 来源页码标注
        pages_found = []
        for c in contexts:
            if isinstance(c, dict):
                pg = pick(c, "page", "page_no", "pages")
                if pg is not None:
                    pages_found.append(str(pg))
                pns = c.get("page_numbers")
                if isinstance(pns, list):
                    pages_found.extend(str(x) for x in pns)
        if pages_found:
            st.caption(f"📌 回答来源页码：第 {', '.join(sorted(set(pages_found)))} 页")
        if rt is not None:
            st.caption(f"⏱️ 响应时间：{rt} 秒　|　模型：{model_used}")

        with st.expander(f"📚 检索到 {len(contexts)} 条上下文", expanded=False):
            _render_contexts(contexts, beta)

    st.session_state["chat_history"].append({
        "role": "assistant", "content": answer, "contexts": contexts,
    })


# 评分公式可视化
with st.expander("🧮 混合检索评分公式", expanded=False):
    st.latex(r"Score_{final} = \beta\cdot Sim_{Dense} + (1-\beta)\cdot Sim_{Rerank}")
    st.write(f"当前 β = **{beta}**（稠密权重），即 `Score = {beta:.2f}·稠密相似度 + {1-beta:.2f}·重排相似度`"
             f"；系统默认 β=0.4，对应 0.4·稠密 + 0.6·重排。")

# 待处理问题（示例按钮触发）
pending = st.session_state.pop("_pending_q", None)
if pending:
    handle_question(pending)

# chat 输入框
user_q = st.chat_input("请输入您的母婴护理相关问题……")
if user_q:
    handle_question(user_q)

if not st.session_state["chat_history"]:
    st.info("👆 选择示例问题，或在下方输入框提问。")
