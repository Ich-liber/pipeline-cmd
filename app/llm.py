"""LLM 客户端封装。

设计要点：
1. 模型解耦：改 .env 就能在 DeepSeek / 通义 / Ollama 之间切换；
2. JSON 强约束：提供 call_llm_json，自动解析 JSON + 失败重试（防格式错乱）；
3. 容错：LLM 调用失败自动重试，连续失败写入 error_log。
"""
import json
import re
import time
from typing import Any

from langchain_openai import ChatOpenAI

from app.config import settings


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """获取 LLM 实例（模型由 .env 决定）。"""
    settings.check()
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=temperature,
    )


def _extract_json(text: str) -> Any:
    """从模型输出中提取 JSON（兼容 ```json 代码块 / 前后杂文本）。"""
    # 优先找 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    # 去掉首尾多余文本，找第一个 { 或 [
    start_candidates = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not start_candidates:
        raise ValueError("输出中未找到 JSON")
    start = min(start_candidates)
    # 从 start 开始尝试解析
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text[start:].strip())
        return obj
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}\n原文片段: {text[start:start+300]}")


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    max_retries: int = 2,
    temperature: float = 0.3,
) -> Any:
    """调用 LLM 并返回结构化 JSON。

    失败时自动重试（把错误回注给模型，要求修正），最多 max_retries 次。
    """
    llm = get_llm(temperature=temperature)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            resp = llm.invoke(messages)
            return _extract_json(resp.content)
        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt < max_retries:
                # 把错误回注，要求重新输出
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": "（上一次输出格式有误，正在修正）"},
                    {"role": "user", "content": f"你上一次的输出不是合法 JSON：{e}。请只输出合法 JSON，不要任何解释文字。"},
                ]
                time.sleep(1)
    raise RuntimeError(f"LLM JSON 调用失败（已重试 {max_retries} 次）: {last_error}")
