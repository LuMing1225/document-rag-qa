# -*- coding: utf-8 -*-
"""
页面 3：知识库管理
==================
- 创建知识库 POST /api/knowledge/create
- 知识库列表 GET /api/knowledge/list
- 选择知识库后展示已解析文档、构建索引 POST /api/knowledge/{kb_id}/index
- 索引构建结果（向量数/分块数/耗时）与索引状态
"""

import sys
from pathlib import Path

import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from utils import (  # noqa: E402
    create_kb, list_kbs, build_index, get_kb_chunks,
)

st.set_page_config(page_title="知识库管理", page_icon="📚", layout="wide")

st.markdown("<div class='breadcrumb'>功能 / 知识库管理</div>", unsafe_allow_html=True)
st.markdown("<div class='page-title'>📚 知识库管理与索引构建</div>", unsafe_allow_html=True)
st.write("创建知识库，将已解析文档入库并构建向量索引。")


def pick(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d.get(k)
    return default


# ---------------------------------------------------------------------------
# 新建知识库
# ---------------------------------------------------------------------------
with st.expander("➕ 创建新知识库", expanded=False):
    with st.form("create_kb_form", clear_on_submit=True):
        kb_name = st.text_input("知识库名称", placeholder="如：母婴护理标准手册库")
        kb_desc = st.text_area("描述", placeholder="该知识库收录的文档范围……")
        submitted = st.form_submit_button("创建")
        if submitted:
            if not kb_name.strip():
                st.warning("请输入知识库名称。")
            else:
                with st.spinner("正在创建知识库……"):
                    resp = create_kb(kb_name.strip(), kb_desc.strip())
                if "error" in resp:
                    st.error(f"❌ 创建失败：{resp['error']}")
                else:
                    st.session_state["kb_create_result"] = resp
                    st.success(f"✅ 知识库创建成功：{pick(resp, 'kb_id', 'id', default='')}")

# ---------------------------------------------------------------------------
# 知识库列表
# ---------------------------------------------------------------------------
st.markdown("### 📂 知识库列表")
kbs = list_kbs()
if not kbs:
    st.info("暂无知识库，请在上方创建。")
else:
    for kb in kbs:
        if not isinstance(kb, dict):
            continue
        kb_id = pick(kb, "kb_id", "id", "knowledge_base_id")
        kb_name = pick(kb, "name", "kb_name", default=kb_id)
        kb_desc = pick(kb, "description", "desc", default="")
        doc_count = pick(kb, "document_count", "docs_count", "num_docs", default="—")
        chunk_count = pick(kb, "chunk_count", "chunks", "num_chunks", default="—")
        indexed = pick(kb, "indexed", "is_indexed", "has_index", default=None)
        idx_status = "✅ 已建索引" if indexed else ("🕒 未建索引" if indexed is not None else "—")

        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(f"**{kb_name}**　`{kb_id}`")
                if kb_desc:
                    st.caption(kb_desc)
            with c2:
                st.metric("文档数", doc_count)
                st.metric("分块数", chunk_count)
            with c3:
                st.markdown(f"索引状态：{idx_status}")
                if kb_id and st.button("构建索引", key=f"idx_{kb_id}", type="primary"):
                    with st.status("正在构建向量索引……", expanded=True) as status:
                        st.write("① 向量化分块并写入向量库……")
                        resp = build_index(kb_id)
                        if "error" in resp:
                            status.update(label="❌ 索引构建失败", state="error")
                            st.error(resp["error"])
                        else:
                            st.session_state["index_result"] = resp
                            status.update(label="✅ 索引构建完成", state="complete")

# ---------------------------------------------------------------------------
# 索引构建结果
# ---------------------------------------------------------------------------
idx_res = st.session_state.get("index_result")
if idx_res and not idx_res.get("error"):
    st.markdown("### 📈 最近一次索引构建结果")
    r1, r2, r3 = st.columns(3)
    r1.metric("向量数量", pick(idx_res, "vector_count", "vectors", default="—"))
    r2.metric("分块数量", pick(idx_res, "chunk_count", "chunks", default="—"))
    r3.metric("耗时(s)", pick(idx_res, "elapsed", "time", "cost", default="—"))
    with st.expander("索引构建返回详情", expanded=False):
        st.json(idx_res)

# ---------------------------------------------------------------------------
# 选择知识库查看已入库分块概览
# ---------------------------------------------------------------------------
if kbs:
    st.markdown("### 🔎 查看知识库分块概览")
    kb_options = {f"{pick(k,'name',default=pick(k,'kb_id',default='?'))}":
                  pick(k, "kb_id", "id") for k in kbs if isinstance(k, dict)}
    sel = st.selectbox("选择知识库查看分块", list(kb_options.keys()))
    sel_id = kb_options[sel]
    if st.button("加载分块概览", key="load_chunks_overview"):
        with st.spinner("加载中……"):
            data = get_kb_chunks(sel_id)
        if "error" in data:
            st.error(data["error"])
        else:
            parents = data.get("parents") or data.get("parent_chunks") or []
            children = data.get("children") or data.get("child_chunks") or data.get("chunks") or []
            g1, g2 = st.columns(2)
            g1.metric("父文档数", len(parents) if isinstance(parents, list) else 0)
            g2.metric("子分块数", len(children) if isinstance(children, list) else 0)
            st.caption("前往「🧩 父子分块查看」可查看完整树形结构。")
