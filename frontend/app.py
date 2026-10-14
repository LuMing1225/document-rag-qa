# -*- coding: utf-8 -*-
"""
千万级长文本复杂版面分析 RAG 检索系统 —— 前端主入口
=====================================================
启动方式：
    conda run -n pdfqa streamlit run frontend/app.py --server.port 8523 --server.headless true

本文件负责：
1. 页面级配置（标题 / 图标 / 宽布局）；
2. 全局样式注入（中文字体 + 母婴蓝主题）；
3. 侧边栏：后端连接状态、模型配置显示、系统信息；
4. 首页：系统架构数据流图 + 快速操作入口。

五个业务页面由 frontend/pages/ 目录自动路由，Streamlit 会在侧边栏
自动生成页面链接，无需手动维护导航列表。
"""

import sys
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# 路径引导：把 frontend/ 目录加入 sys.path，使本文件与 pages/ 下脚本都能 import utils
# ---------------------------------------------------------------------------
FRONTEND_DIR = Path(__file__).resolve().parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from utils import check_backend, get_health  # noqa: E402

# ---------------------------------------------------------------------------
# 1. 页面配置（必须是第一条 st 命令）
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="长文本版面分析RAG检索系统",
    page_icon="🧸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# 2. 全局样式注入
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
    html, body, [class*="css"] {
        font-family: "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB",
                     "Source Han Sans SC", sans-serif;
    }
    .stApp { background-color: #F4F7FB; }

    .stButton > button[kind="primary"] {
        background-color: #2A6F97; border: none; border-radius: 8px;
    }
    .stButton > button[kind="primary"]:hover { background-color: #1F5A7E; }
    .stButton > button:not([kind="primary"]) { border-radius: 8px; }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1F3A5F 0%, #16293F 100%);
        color: #E6EDF3;
    }
    [data-testid="stSidebar"] * { color: #E6EDF3 !important; }

    .metric-card {
        background: #FFFFFF; border-left: 4px solid #2A6F97;
        border-radius: 10px; padding: 16px 20px;
        box-shadow: 0 2px 8px rgba(31, 58, 95, 0.08); margin-bottom: 12px;
    }
    .breadcrumb { color: #6B7A8F; font-size: 0.85rem; margin-bottom: 4px; }
    .page-title {
        color: #1F3A5F; font-size: 1.7rem; font-weight: 700; margin-bottom: 6px;
    }
    .status-dot {
        display: inline-block; width: 10px; height: 10px;
        border-radius: 50%; margin-right: 6px;
    }
    .dot-ok   { background-color: #2ECC71; }
    .dot-warn { background-color: #F39C12; }
    .dot-down { background-color: #E74C3C; }

    .flow-node {
        background: #FFFFFF; border: 1px solid #D6E2EE; border-radius: 10px;
        padding: 10px 6px; text-align: center; font-size: 0.82rem;
        color: #1F3A5F; font-weight: 600;
        box-shadow: 0 1px 4px rgba(31,58,95,0.06);
    }
    .flow-arrow { text-align: center; color: #2A6F97; font-size: 1.1rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 3. session_state 全局状态初始化
# ---------------------------------------------------------------------------
DEFAULTS = {
    "kb_id": None,
    "kb_name": None,
    "doc_id": None,
    "doc_filename": None,
    "parse_result": None,
    "chat_history": [],
    "backend_ok": False,
    "health_info": {},
}
for key, val in DEFAULTS.items():
    st.session_state.setdefault(key, val)


# ---------------------------------------------------------------------------
# 4. 启动时探测后端健康状态（10 秒缓存）
# ---------------------------------------------------------------------------
@st.cache_data(ttl=10, show_spinner=False)
def _probe_health():
    ok = check_backend()
    info = get_health() if ok else {}
    return ok, info


backend_ok, health_info = _probe_health()
st.session_state["backend_ok"] = backend_ok
st.session_state["health_info"] = health_info

# ---------------------------------------------------------------------------
# 5. 侧边栏：系统标题 + 连接状态 + 模型配置
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<h2 style='color:#FFFFFF;margin-bottom:2px;'>🧸 母婴护理知识库</h2>"
        "<p style='color:#9FB3C8;font-size:0.82rem;margin-bottom:14px;'>"
        "千万级长文本复杂版面分析 RAG 检索系统</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("### 🔌 后端连接")
    if backend_ok:
        st.markdown(
            "<span class='status-dot dot-ok'></span>"
            "<span style='font-size:0.9rem;'>后端服务：在线 (8563)</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<span class='status-dot dot-down'></span>"
            "<span style='font-size:0.9rem;'>后端服务：离线 (8563)</span>",
            unsafe_allow_html=True,
        )

    ollama_status = health_info.get("ollama", "unknown") if health_info else "unknown"
    if backend_ok and ollama_status == "ok":
        st.markdown(
            "<span class='status-dot dot-ok'></span>"
            "<span style='font-size:0.9rem;'>Ollama：就绪</span>",
            unsafe_allow_html=True,
        )
    elif backend_ok:
        st.markdown(
            "<span class='status-dot dot-warn'></span>"
            "<span style='font-size:0.9rem;'>Ollama：未就绪</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<span class='status-dot dot-down'></span>"
            "<span style='font-size:0.9rem;'>Ollama：未连接</span>",
            unsafe_allow_html=True,
        )

    st.markdown("### ⚙️ 模型配置")
    cfg = health_info.get("config", {}) if isinstance(health_info, dict) else {}
    if cfg:
        st.markdown(
            f"<div style='font-size:0.8rem;line-height:1.7;'>"
            f"• 嵌入模型：<b>{cfg.get('embedding_model', cfg.get('embed_model', '—'))}</b><br/>"
            f"• 生成模型：<b>{cfg.get('llm_model', cfg.get('generator', '—'))}</b><br/>"
            f"• 重排器：<b>{cfg.get('reranker', cfg.get('rerank_model', '—'))}</b>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='font-size:0.8rem;color:#9FB3C8;'>"
            "后端在线后自动显示模型配置</div>",
            unsafe_allow_html=True,
        )

    models = health_info.get("models", {}) if isinstance(health_info, dict) else {}
    if models:
        with st.expander("已加载模型明细", expanded=False):
            for mname, mstate in models.items():
                color = "#2ECC71" if mstate == "ok" else "#F39C12"
                st.markdown(
                    f"<div style='font-size:0.8rem;'>• {mname}："
                    f"<span style='color:{color};'>{mstate}</span></div>",
                    unsafe_allow_html=True,
                )

    st.divider()
    st.markdown(
        "<div style='font-size:0.75rem;color:#7A8CA0;'>"
        "前端 v1.0 · 端口 8523<br/>后端 API · :8563<br/>"
        "© 2026 母婴护理连锁集团</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# 6. 主区域：首页概览
# ---------------------------------------------------------------------------
st.markdown("<div class='breadcrumb'>首页 / 系统概览</div>", unsafe_allow_html=True)
st.markdown("<div class='page-title'>千万级长文本复杂版面分析 RAG 检索系统</div>", unsafe_allow_html=True)
st.write(
    "面向 **母婴护理连锁机构集团知识库**，针对长文本复杂版面（双栏、表格、图文混排）"
    "进行版面分析与父子分块，构建向量索引，通过 **稠密检索 + 重排** 的混合检索策略，"
    "为护理人员提供精准、可溯源的智能问答。"
)

# 系统架构数据流
st.markdown("#### 🔄 系统数据流")
flow = [
    ("📄 PDF上传", "原始文档"),
    ("🔍 版面分析", "区域/双栏/表格"),
    ("🧩 父子分块", "Parent-Child"),
    ("📚 向量索引", "Embedding"),
    ("🔎 混合检索", "Dense+Rerank"),
    ("🤖 LLM生成", "可溯源回答"),
]
cols = st.columns(len(flow) * 2 - 1)
for i, (title, sub) in enumerate(flow):
    node_idx = i * 2
    with cols[node_idx]:
        st.markdown(
            f"<div class='flow-node'>{title}<br/>"
            f"<span style='font-size:0.72rem;color:#6B7A8F;font-weight:400;'>{sub}</span></div>",
            unsafe_allow_html=True,
        )
    if node_idx < len(cols) - 1:
        with cols[node_idx + 1]:
            st.markdown("<div class='flow-arrow'>➜</div>", unsafe_allow_html=True)

st.markdown("")

# 功能卡片 + 快速操作
st.markdown("#### 🚀 快速操作")
pages = [
    ("1_📄_PDF版面分析", "📄", "PDF上传与版面分析可视化", "PDF 版面分析"),
    ("2_🧩_父子分块查看", "🧩", "父子分块树形结构", "父子分块"),
    ("3_📚_知识库管理", "📚", "知识库创建与索引构建", "知识库管理"),
    ("4_💬_智能问答", "💬", "RAG 问答与来源溯源", "开始问答"),
    ("5_📊_系统监控", "📊", "健康检查与检索性能", "系统监控"),
]
pc = st.columns(5)
for col, (page_name, icon, desc, btn_label) in zip(pc, pages):
    with col:
        st.markdown(
            f"<div class='metric-card' style='min-height:120px;'>"
            f"<div style='font-size:1.6rem;'>{icon}</div>"
            f"<b style='font-size:0.95rem;'>{page_name.split('_',1)[1]}</b><br/>"
            f"<span style='font-size:0.78rem;color:#6B7A8F;'>{desc}</span></div>",
            unsafe_allow_html=True,
        )
        if st.button(btn_label, key=f"go_{page_name}", use_container_width=True):
            st.switch_page(f"pages/{page_name}.py")

st.info(
    "👈 首次使用流程：① **PDF版面分析**（上传并解析文档）→ ② **父子分块查看**（检查分块结构）"
    "→ ③ **知识库管理**（创建库并构建索引）→ ④ **智能问答** → ⑤ **系统监控**。"
)
