# -*- coding: utf-8 -*-
"""
页面 1：PDF 版面分析
====================
- 上传 PDF → POST /api/parse/upload
- 展示文档基本信息、版面区域分布、双栏检测、表格提取结果
- 用 pypdfium2 在前端本地渲染页面缩略图，左右对比页面图与文本块
"""

import sys
from pathlib import Path

import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from utils import upload_pdf, get_parse_result  # noqa: E402

st.set_page_config(page_title="PDF版面分析", page_icon="📄", layout="wide")

st.markdown("<div class='breadcrumb'>功能 / PDF 版面分析</div>", unsafe_allow_html=True)
st.markdown("<div class='page-title'>📄 PDF 上传与版面分析</div>", unsafe_allow_html=True)
st.write("上传母婴护理相关 PDF 文档，后端将进行版面分析（区域识别、双栏检测、表格提取）。")


# ---------------------------------------------------------------------------
# 容错取值工具：从结构不确定的解析结果中按候选键列表取值
# ---------------------------------------------------------------------------
def pick(d: dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d.get(k)
    return default


def render_page_thumbnails(file_bytes, max_pages=6, scale=1.2):
    """用 pypdfium2 在前端本地渲染 PDF 页面缩略图，返回 PIL 图像列表。"""
    try:
        import io
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(io.BytesIO(file_bytes))
        imgs = []
        n = len(pdf)
        for i in range(min(n, max_pages)):
            page = pdf[i]
            bitmap = page.render(scale=scale)
            imgs.append(bitmap.to_pil())
        return imgs, n
    except Exception as exc:  # noqa: BLE001
        st.warning(f"页面缩略图渲染失败（不影响解析结果）：{exc}")
        return [], 0


# ---------------------------------------------------------------------------
# 上传区
# ---------------------------------------------------------------------------
uploaded = st.file_uploader("选择 PDF 文件", type=["pdf"], key="pdf_uploader")

if uploaded is not None:
    file_bytes = uploaded.getvalue()
    # 缓存文件字节，供渲染缩略图使用
    st.session_state["uploaded_bytes"] = file_bytes
    st.session_state["uploaded_name"] = uploaded.name

    if st.button("🚀 上传并开始版面分析", type="primary", key="do_parse"):
        with st.status("正在上传并解析 PDF，请稍候……", expanded=True) as status:
            st.write("① 上传文件到后端……")
            resp = upload_pdf(uploaded)
            if "error" in resp:
                status.update(label="上传/解析失败", state="error")
                st.error(f"❌ {resp['error']}")
            else:
                st.write("② 解析完成，拉取版面分析结果……")
                doc_id = pick(resp, "doc_id", "id", "document_id")
                st.session_state["doc_id"] = doc_id
                st.session_state["doc_filename"] = pick(resp, "filename", "name", uploaded.name)
                # 上传接口只返回摘要（layout_regions），需拉取完整结果（含chunks/tables）
                result = get_parse_result(doc_id) if doc_id else resp
                if not result or result.get("error"):
                    result = resp  # 降级用上传摘要
                st.session_state["parse_result"] = result
                status.update(label="✅ 版面分析完成", state="complete")

# ---------------------------------------------------------------------------
# 结果展示区
# ---------------------------------------------------------------------------
result = st.session_state.get("parse_result")

if result and not result.get("error"):
    st.divider()
    st.markdown("### 📋 文档基本信息")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("文件名", st.session_state.get("doc_filename", pick(result, "filename", "name", "—")))
    c2.metric("页数", pick(result, "total_pages", "pages_count", "num_pages", default="—"))
    c3.metric("解析耗时(s)", pick(result, "elapsed", "parse_time", "cost", default="—"))
    c4.metric("文档ID", str(pick(result, "doc_id", "id", default="—"))[:18])

    # ---- 版面区域分布（从 layout_regions 扁平数组统计） ----
    st.markdown("### 🧱 版面区域类型分布")
    layout_regions = pick(result, "layout_regions", "regions", default=[])
    tables_data = pick(result, "tables", default=[])
    chunks_data = pick(result, "chunks", "blocks", default=[])

    region_counts = {"标题": 0, "正文": 0, "表格": 0, "图片": 0, "其他": 0}
    type_map = {
        "title": "标题", "heading": "标题", "header": "标题",
        "text": "正文", "body": "正文", "paragraph": "正文",
        "table": "表格",
        "image": "图片", "figure": "图片", "picture": "图片",
    }
    if isinstance(layout_regions, list):
        for rg in layout_regions:
            if not isinstance(rg, dict):
                continue
            rtype = str(pick(rg, "type", "category", "label", default="")).lower()
            mapped = type_map.get(rtype, "其他" if rtype else "其他")
            region_counts[mapped] += 1

    rc = st.columns(5)
    rc[0].metric("标题区域", region_counts["标题"])
    rc[1].metric("正文区域", region_counts["正文"])
    rc[2].metric("表格区域", region_counts["表格"])
    rc[3].metric("图片区域", region_counts["图片"])
    rc[4].metric("其他区域", region_counts["其他"])

    # ---- 双栏检测（column字段 + bbox坐标兜底） ----
    st.markdown("### 📑 双栏排版检测")
    two_col_pages = set()
    if isinstance(layout_regions, list):
        for rg in layout_regions:
            if isinstance(rg, dict):
                col = str(pick(rg, "column", default="")).lower()
                if col in ("left", "right"):
                    pno = pick(rg, "page_number", "page", "page_no", default="?")
                    two_col_pages.add(str(pno))
    # 兜底：基于bbox坐标检测双栏（每页文本区域同时存在左半区和右半区）
    if not two_col_pages and isinstance(layout_regions, list):
        page_text_x = {}
        for rg in layout_regions:
            if not isinstance(rg, dict):
                continue
            if str(pick(rg, "type", default="")).lower() not in ("text", "title", "table"):
                continue
            bbox = pick(rg, "bbox", default=None)
            pno = str(pick(rg, "page_number", "page", default="?"))
            if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                x0, y0, x1, y1 = bbox[:4]
                if (x1 - x0) < 280:
                    page_text_x.setdefault(pno, []).append((x0, x1))
        for pno, xs in page_text_x.items():
            has_left = any(x0 < 290 for x0, x1 in xs)
            has_right = any(x1 > 305 for x0, x1 in xs)
            if has_left and has_right:
                two_col_pages.add(pno)
    if not two_col_pages:
        extra = pick(result, "two_column_pages", "double_column_pages", default=[])
        if isinstance(extra, list):
            two_col_pages = set(str(x) for x in extra)
    if two_col_pages:
        sorted_pages = sorted(two_col_pages, key=lambda x: int(x) if x.isdigit() else 0)
        st.success(f"检测到 **{len(two_col_pages)}** 页为双栏排版：第 {', '.join(sorted_pages)} 页")
    else:
        st.info("未检测到双栏排版页面（或后端未返回该信息）。")

    # ---- 表格提取结果（直接从 tables 数组取 markdown） ----
    st.markdown("### 📊 表格提取结果（Markdown）")
    tables_md = []
    if isinstance(tables_data, list):
        for t in tables_data:
            if isinstance(t, dict):
                md = pick(t, "markdown", "table_markdown", "content", "text")
                if md:
                    tables_md.append(str(md))
    if tables_md:
        for idx, md in enumerate(tables_md, 1):
            with st.expander(f"表格 {idx}（{len(md)} 字符）", expanded=(idx == 1)):
                st.markdown(md)
    else:
        st.info("未提取到表格（或表格内容为空）。")

    # ---- 左右对比：页面缩略图 vs 提取文本块 ----
    st.markdown("### 🖼️ 页面渲染 vs 提取文本块")
    file_bytes = st.session_state.get("uploaded_bytes")
    thumb_imgs, total_pages = render_page_thumbnails(file_bytes) if file_bytes else ([], 0)

    # 收集文本块（从 chunks 数组取 text）
    text_blocks = []
    if isinstance(chunks_data, list):
        for c in chunks_data:
            if isinstance(c, dict):
                t = pick(c, "text", "content")
                if t:
                    text_blocks.append(str(t))
    if not text_blocks and isinstance(layout_regions, list):
        for rg in layout_regions:
            if isinstance(rg, dict):
                t = pick(rg, "text", "content")
                if t and str(t).strip():
                    text_blocks.append(str(t))

    left, right = st.columns(2)
    with left:
        st.caption("左侧：PDF 页面渲染图（前6页）")
        if thumb_imgs:
            for i, im in enumerate(thumb_imgs, 1):
                st.image(im, caption=f"第 {i} 页", use_container_width=True)
        else:
            st.info("暂无页面渲染图。")
    with right:
        st.caption(f"右侧：提取的文本块（共{len(text_blocks)}块）")
        if text_blocks:
            for i, t in enumerate(text_blocks[:30], 1):
                with st.expander(f"文本块 {i}（{len(t)} 字）", expanded=(i == 1)):
                    st.write(t[:1500])
        else:
            st.info("暂无提取文本块。")

elif result and result.get("error"):
    st.error(f"❌ 解析结果获取失败：{result['error']}")
else:
    st.info("👆 请先上传 PDF 文件并点击「上传并开始版面分析」。")
