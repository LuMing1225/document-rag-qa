"""
LLM 生成器（Generator）

通过 Ollama /api/chat 调用 qwen3:8b，基于检索到的父文档生成答案。

- 系统提示词：母婴护理领域专家，严格依据知识库内容回答
- 上下文：父文档按分数排序拼接，标注来源页码
- 同时提供非流式 generate() 与流式 generate_stream()
"""
import logging
from typing import Generator as GenType, List

import requests

from backend.config import (
    GENERATION_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_TIMEOUT,
)
from backend.models import RetrievedParent

logger = logging.getLogger(__name__)

# 系统提示词：限定为母婴护理垂直领域
SYSTEM_PROMPT = """你是一位资深的母婴护理领域专家（涵盖科学喂养、新生儿护理、常见疾病预防与居家护理预案）。
请严格依据下面提供的知识库内容回答用户问题。

要求：
1. 答案必须基于检索到的知识库内容，不要编造；若知识库中没有相关信息，明确说明"根据现有知识库无法确定"。
2. 回答要专业、准确、条理清晰，必要时分点说明。
3. 涉及用药、剂量、疾病处置时，提醒"如有疑问请及时就医"。
4. 在答案末尾用括号标注信息来源页码，例如（来源：第3页、第7页）。
5. 必须输出完整答案，不要返回空内容。
"""


class Generator:
    """RAG 答案生成器。"""

    def __init__(self) -> None:
        self.chat_url = f"{OLLAMA_BASE_URL}/api/chat"
        self.model = GENERATION_MODEL

    # ------------------------------------------------------------------ #
    # 非流式
    # ------------------------------------------------------------------ #
    def generate(self, question: str, parents: List[RetrievedParent]) -> str:
        """非流式生成答案。"""
        context = self._build_context(parents)
        answer = self._call_chat(self.model, question, context, stream=False)
        if not answer or len(answer.strip()) < 2:
            logger.warning("模型 %s 返回空答案", self.model)
        return answer.strip() or "（模型未返回内容）"

    # ------------------------------------------------------------------ #
    # 流式
    # ------------------------------------------------------------------ #
    def generate_stream(self, question: str, parents: List[RetrievedParent]) -> GenType[str, None, None]:
        """流式生成答案，逐段 yield 文本增量。"""
        context = self._build_context(parents)
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{context}\n\n【问题】{question}\n\n【请回答】"},
                ],
                "stream": True,
                "options": {"temperature": 0.2, "num_predict": 1024},
            }
            with requests.post(self.chat_url, json=payload, stream=True, timeout=OLLAMA_TIMEOUT) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    import json
                    try:
                        data = json.loads(line.decode("utf-8"))
                    except Exception:
                        continue
                    delta = data.get("message", {}).get("content", "")
                    if delta:
                        yield delta
                    if data.get("done"):
                        break
        except Exception as e:
            logger.exception("流式生成失败: %s", e)
            yield "\n（流式生成失败）"

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #
    def _call_chat(self, model: str, question: str, context: str, stream: bool) -> str:
        """调用 Ollama /api/chat（非流式）。"""
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{context}\n\n【问题】{question}\n\n【请回答】"},
                ],
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 1024},
            }
            logger.info("调用生成模型 %s, 上下文长度=%d", model, len(context))
            resp = requests.post(self.chat_url, json=payload, timeout=OLLAMA_TIMEOUT)
            resp.raise_for_status()
            answer = resp.json().get("message", {}).get("content", "").strip()
            logger.info("模型 %s 返回 %d 字符", model, len(answer))
            return answer
        except Exception as e:
            logger.exception("生成答案失败(model=%s): %s", model, e)
            return ""

    @staticmethod
    def _build_context(parents: List[RetrievedParent]) -> str:
        """把检索到的父文档按分数排序拼接为上下文，并标注页码。"""
        parts: List[str] = ["【知识库检索到的参考内容】"]
        if not parents:
            parts.append("（未检索到相关内容）")
            return "\n".join(parts)

        for i, p in enumerate(parents, 1):
            pages = p.page_numbers or []
            page_str = "、".join(str(pg) for pg in sorted(set(pages)))
            tag = f"[参考{i}|第{page_str}页]" if page_str else f"[参考{i}]"
            text = p.text
            # 父文档可能较长，限制单个父文档送入 LLM 的长度，避免 prompt 爆炸
            if len(text) > 2000:
                text = text[:2000] + "……"
            parts.append(f"{tag}\n{text}")
        return "\n\n".join(parts)
