# -*- coding: utf-8 -*-
"""
页面 2：父子分块查看
====================
- 选择知识库，拉取父子分块结构 GET /api/knowledge/{kb_id}/chunks
- 树形展示：父文档卡片 → 展开显示子文档
- 统计：父/子总数、平均子文档数、平均字数
"""

import sys
from pathlib import Path

import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from utils import list_kbs, get_kb_chunks  # noqa: E402

st.set_page_config(page_title="父子分块查看", page_icon="🧩", layout="wide")

st.markdown("<div class='breadcrumb'>功能 / 父子分块查看</div>", unsafe_allow_html=True)
st.markdown("<div class='page-title'>🧩 父子分块结构查看</div>", unsafe_allow_html=True)
st.write("选择知识库，查看 Parent-Child 分块的层级结构与分块质量指标。")


def pick(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d.get(k)
    return default


# ---------------------------------------------------------------------------
# 选择知识库
# ---------------------------------------------------------------------------
kbs = list_kbs()
if not kbs:
    st.warning("⚠️ 暂无可用知识库，请先到「📚 知识库管理」创建知识库并构建索引。")
    st.stop()

kb_options = {}
for kb in kbs:
    kb_id = pick(kb, "kb_id", "id", "knowledge_base_id")
    kb_name = pick(kb, "name", "kb_name", default=str(kb_id))
    if kb_id:
        kb_options[f"{kb_name}（{kb_id}）"] = kb_id

sel_label = st.selectbox("选择知识库", list(kb_options.keys()))
kb_id = kb_options[sel_label]
st.session_state["kb_id"] = kb_id

# ---------------------------------------------------------------------------
# 拉取分块结构
# ---------------------------------------------------------------------------
if st.button("🔄 加载父子分块结构", type="primary"):
    with st.spinner("正在拉取分块结构……"):
        data = get_kb_chunks(kb_id)
        st.session_state["chunks_data"] = data

data = st.session_state.get("chunks_data")

if not data:
    st.info("👆 请选择知识库并点击「加载父子分块结构」。")
    st.stop()

if "error" in data:
    st.error(f"❌ 分块结构获取失败：{data['error']}")
    st.stop()

# ---- 容错解析父子列表 ----
parents = data.get("parents") or data.get("parent_chunks") or []
children = data.get("children") or data.get("child_chunks") or []

# 若后端直接给带 children 的 parent 列表，则展开
if not children and isinstance(parents, list):
    flat_children = []
    for p in parents:
        if isinstance(p, dict) and isinstance(p.get("children"), list):
            flat_children.extend(p["children"])
    children = flat_children

# 若后端只给一个 chunks 列表，按 parent_id 归组
if not parents and not children and isinstance(data.get("chunks"), list):
    chunks = data["chunks"]
    parent_map = {}
    for c in chunks:
        pid = pick(c, "parent_id", default="__root__")
        parent_map.setdefault(pid, []).append(c)
    parents = [{"parent_id": pid, "_children": kids} for pid, kids in parent_map.items()]
    children = chunks

# 建立 parent_id -> children 映射
child_by_parent = {}
if isinstance(children, list):
    for c in children:
        if isinstance(c, dict):
            pid = pick(c, "parent_id", "parent", default="__root__")
            child_by_parent.setdefault(pid, []).append(c)

# ---- 统计 ----
total_parents = len(parents) if isinstance(parents, list) else 0
total_children = len(children) if isinstance(children, list) else 0
avg_child = (total_children / total_parents) if total_parents else 0

def _wordcount(text):
    return len(str(text)) if text else 0

parent_words = []
child_words = []
if isinstance(parents, list):
    for p in parents:
        parent_words.append(_wordcount(pick(p, "text", "content")))
if isinstance(children, list):
    for c in children:
        child_words.append(_wordcount(pick(c, "text", "content")))

avg_pw = sum(parent_words) / len(parent_words) if parent_words else 0
avg_cw = sum(child_words) / len(child_words) if child_words else 0

st.markdown("### 📈 分块统计")
m = st.columns(5)
m[0].metric("父文档总数", total_parents)
m[1].metric("子文档总数", total_children)
m[2].metric("平均每父文档子文档数", f"{avg_child:.1f}")
m[3].metric("父文档平均字数", f"{avg_pw:.0f}")
m[4].metric("子文档平均字数", f"{avg_cw:.0f}")

# 后端自带 stats 兜底展示
stats = data.get("stats")
if isinstance(stats, dict):
    with st.expander("后端返回的分块统计（原始）", expanded=False):
        st.json(stats)

# ---- 树形展示 ----
st.markdown("### 🌳 父子分块树形结构")
if isinstance(parents, list) and parents:
    for idx, p in enumerate(parents, 1):
        if not isinstance(p, dict):
            continue
        pid = pick(p, "parent_id", "id", default=f"parent_{idx}")
        ptext = pick(p, "text", "content", default="")
        pwords = _wordcount(ptext)
        page_range = pick(p, "page_range", "pages", default="—")
        kids = child_by_parent.get(pid) or p.get("_children") or p.get("children") or []
        kid_count = len(kids) if isinstance(kids, list) else 0

        with st.expander(
            f"📦 父文档 #{idx} · {pid} ｜ {pwords} 字 ｜ 页码 {page_range} ｜ 含 {kid_count} 个子块",
            expanded=(idx == 1),
        ):
            st.markdown(f"**父文档预览：** {str(ptext)[:300]}")
            if isinstance(kids, list) and kids:
                for j, c in enumerate(kids, 1):
                    if not isinstance(c, dict):
                        continue
                    cid = pick(c, "child_id", "id", default=f"child_{j}")
                    ctext = pick(c, "text", "content", default="")
                    cwords = _wordcount(ctext)
                    layout = pick(c, "layout_type", "type", "category", default="—")
                    page = pick(c, "page", "page_no", "page_num", default="—")
                    st.markdown(
                        f"<div style='margin-left:12px;border-left:3px solid #2A6F97;"
                        f"padding-left:10px;margin-bottom:8px;'>"
                        f"<b>└─ 子块 #{j} · {cid}</b>　"
                        f"<span style='color:#6B7A8F;font-size:0.8rem;'>"
                        f"{cwords} 字 · 布局 {layout} · 第 {page} 页</span><br/>"
                        f"<span style='font-size:0.85rem;'>{str(ctext)[:180]}</span></div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("（该父文档下暂无子块）")
else:
    st.info("该知识库暂无可展示的父子分块，请先构建索引。")
