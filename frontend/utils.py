# -*- coding: utf-8 -*-
"""
前端工具函数模块
================
封装所有与后端 FastAPI 服务 (http://localhost:8563) 的 HTTP 交互。
页面层只允许调用本模块暴露的函数，禁止在页面中直接使用 requests。

设计要点：
- 所有请求统一带超时，避免前端无限等待；
- 所有异常被捕获并转为 dict / list 返回，页面层据此显示友好提示，不会崩溃；
- 对后端返回结构做容错解析，字段名不固定时尽量多路径取值。
"""

from typing import Any, Dict, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# 常量配置
# ---------------------------------------------------------------------------
# 后端 API 基础地址（FastAPI 后端运行在 8563）
API_BASE: str = "http://localhost:8563"

# 统一请求超时（秒）：上传/解析/建索引等长操作由后端同步或异步处理，
# 这里的超时保护单次 HTTP 调用本身不挂死。
REQUEST_TIMEOUT: int = 30

# 问答 / 建索引等长耗时操作使用更长超时
LONG_TIMEOUT: int = 180


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------
def _safe_request(
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    timeout: int = REQUEST_TIMEOUT,
) -> Tuple[bool, Any]:
    """
    统一的 HTTP 请求封装。

    返回 (ok, data)：
    - ok=True  ：HTTP 2xx，data 为解析后的 JSON（或空 dict）；
    - ok=False ：网络异常 / 超时 / 非 2xx，data 为错误信息字符串。
    """
    try:
        resp = requests.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            files=files,
            timeout=timeout,
        )
        if resp.status_code >= 400:
            try:
                err_payload = resp.json()
                err_msg = err_payload.get("detail") or err_payload.get("message") or str(err_payload)
            except Exception:
                err_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            return False, err_msg

        if resp.text:
            try:
                return True, resp.json()
            except Exception:
                return True, {"raw": resp.text}
        return True, {}

    except requests.exceptions.Timeout:
        return False, f"请求超时（>{timeout}秒），后端可能正在处理或未响应"
    except requests.exceptions.ConnectionError:
        return False, "无法连接后端服务，请确认后端已启动（端口 8563）"
    except Exception as exc:  # noqa: BLE001 - 兜底，保证页面不崩
        return False, f"请求异常：{exc}"


# ---------------------------------------------------------------------------
# 系统健康检查 / 配置
# ---------------------------------------------------------------------------
def check_backend() -> bool:
    """检查后端是否可连通。GET {API_BASE}/health"""
    ok, _ = _safe_request("GET", f"{API_BASE}/health", timeout=5)
    return ok


def get_health() -> Dict[str, Any]:
    """
    获取后端健康详情。
    约定返回形如：
        {"status": "ok", "ollama": "ok", "models": {...},
         "config": {"embedding_model": ..., "llm_model": ..., "reranker": ...}}
    做容错包装，缺失字段返回空结构。
    """
    ok, data = _safe_request("GET", f"{API_BASE}/health", timeout=5)
    if not ok:
        return {"status": "down", "ollama": "down", "models": {}, "config": {}}
    if isinstance(data, dict):
        data.setdefault("models", {})
        data.setdefault("config", {})
        return data
    return {"status": "ok", "raw": str(data), "models": {}, "config": {}}


# ---------------------------------------------------------------------------
# 解析相关 API
# ---------------------------------------------------------------------------
def upload_pdf(file) -> Dict[str, Any]:
    """
    上传 PDF 文件到后端并触发解析。
    POST /api/parse/upload  (multipart/form-data, 字段名 file)
    成功返回 {"doc_id": "...", "filename": "...", ...}，失败返回 {"error": "..."}
    """
    filename = getattr(file, "name", "upload.pdf")
    files = {"file": (filename, file.getvalue(), "application/pdf")}
    ok, data = _safe_request("POST", f"{API_BASE}/api/parse/upload",
                             files=files, timeout=LONG_TIMEOUT)
    if not ok:
        return {"error": data}
    return data if isinstance(data, dict) else {"error": "返回格式异常"}


def get_parse_result(doc_id: str) -> Dict[str, Any]:
    """
    获取文档解析结果。
    GET /api/parse/{doc_id}
    返回文档基本信息 + 版面分析结果（区域分布 / 双栏 / 表格 / 文本块）。
    """
    ok, data = _safe_request("GET", f"{API_BASE}/api/parse/{doc_id}", timeout=60)
    if not ok:
        return {"error": data}
    return data if isinstance(data, dict) else {"error": "返回格式异常"}


# ---------------------------------------------------------------------------
# 知识库相关 API
# ---------------------------------------------------------------------------
def create_kb(name: str, description: str = "") -> Dict[str, Any]:
    """创建新知识库。POST /api/knowledge/create  JSON: {"name", "description"}"""
    ok, data = _safe_request(
        "POST",
        f"{API_BASE}/api/knowledge/create",
        json_body={"name": name, "description": description},
    )
    if not ok:
        return {"error": data}
    return data if isinstance(data, dict) else {"error": "返回格式异常"}


def list_kbs() -> List[Dict[str, Any]]:
    """
    获取知识库列表。GET /api/knowledge/list
    返回 list[知识库]，失败返回空列表。
    """
    ok, data = _safe_request("GET", f"{API_BASE}/api/knowledge/list")
    if not ok:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("kbs", "knowledge_bases", "items", "data"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def build_index(kb_id: str) -> Dict[str, Any]:
    """
    为知识库构建向量索引。
    POST /api/knowledge/{kb_id}/index
    返回 {"vector_count": ..., "chunk_count": ..., "elapsed": ..., ...}
    """
    ok, data = _safe_request(
        "POST", f"{API_BASE}/api/knowledge/{kb_id}/index", timeout=LONG_TIMEOUT
    )
    if not ok:
        return {"error": data}
    return data if isinstance(data, dict) else {"error": "返回格式异常"}


def get_kb_chunks(kb_id: str) -> Dict[str, Any]:
    """
    获取知识库的父子分块结构。
    GET /api/knowledge/{kb_id}/chunks → {total, items:[parent...]}
    再逐个拉取子块 GET /api/chunks/{kb_id}/children/{parent_id}
    返回 {"parents": [...], "children": [...]}。
    """
    ok, data = _safe_request("GET", f"{API_BASE}/api/knowledge/{kb_id}/chunks", timeout=60)
    if not ok:
        return {"error": data}
    if not isinstance(data, dict):
        return {"error": "返回格式异常"}

    # 后端返回 items（父块列表），兼容前端期望的 parents 字段
    parents = data.get("items") or data.get("parents") or data.get("parent_chunks") or []
    children = list(data.get("children") or data.get("child_chunks") or [])

    # 逐个父块拉取子块
    for p in parents:
        if not isinstance(p, dict):
            continue
        pid = p.get("parent_id") or p.get("id")
        if not pid:
            continue
        ok_c, cdata = _safe_request(
            "GET", f"{API_BASE}/api/chunks/{kb_id}/children/{pid}", timeout=30
        )
        if ok_c and isinstance(cdata, dict):
            clist = cdata.get("children") or []
            for c in clist:
                if isinstance(c, dict):
                    c.setdefault("parent_id", pid)
            children.extend(clist)

    return {"parents": parents, "children": children, "total": len(parents)}


def get_kb_stats(kb_id: str = "") -> Dict[str, Any]:
    """
    获取知识库/系统统计信息。
    GET /api/knowledge/stats  （可选 ?kb_id=）
    后端若未提供，做容错返回空 dict。
    """
    url = f"{API_BASE}/api/knowledge/stats"
    if kb_id:
        url += f"?kb_id={kb_id}"
    ok, data = _safe_request("GET", url)
    if not ok:
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# 问答相关 API
# ---------------------------------------------------------------------------
def query(question: str, kb_id: str, top_k: int = 6,
          beta: float = 0.6) -> Dict[str, Any]:
    """
    提问（混合检索 + 重排 + 生成）。
    POST /api/chat/query
    body: {"question", "kb_id", "top_k", "beta"}
    返回 {"answer", "contexts": [...], "response_time", "model_used"}
    """
    body: Dict[str, Any] = {
        "question": question,
        "kb_id": kb_id,
        "top_k": top_k,
        "beta": beta,
    }
    ok, data = _safe_request("POST", f"{API_BASE}/api/chat/query",
                             json_body=body, timeout=LONG_TIMEOUT)
    if not ok:
        return {"error": data}
    return data if isinstance(data, dict) else {"error": "返回格式异常"}
