"""LLM 客户端：OpenAI 兼容 /chat/completions，配置全部走环境变量（决策 D8）。

未配置环境变量 → LLM 功能整体禁用，规则通路不受影响；客户端必配
enable_thinking=false（qwen3 系提速）、max_tokens 截断 JSON 修复、超时+有限重试。
M4 交付。

实现口径（plan/04 §三 + HANDOFF-M4）：
- 传输层用标准库 urllib（core 零第三方依赖，断网/未配置环境零行为差异）；
  pyproject 的 llm extra（httpx）保留给 Web TestClient 等测试期用途；
- 所有异常收敛为 LLMError（调用方据此降级到纯规则通路，绝不中断主流程）；
- 输出文本剥离 <think> 块与 ```json 围栏（qwen 系/通用回复形态），截断 JSON
  尝试最小修复（截取首个 { 或 [ 起始的子串）后仍失败 → LLMError；
- 摘录类输出必须过"原文子串"校验后才能进入参数卡（校验在 llm/fallback.py）。
"""
import json
import os
import time
import urllib.error
import urllib.request

ENV_BASE_URL = "BIDCHECKER_LLM_BASE_URL"
ENV_API_KEY = "BIDCHECKER_LLM_API_KEY"
ENV_MODEL = "BIDCHECKER_LLM_MODEL"


class LLMError(RuntimeError):
    """LLM 调用失败（未配置/网络不可达/响应不合法）。调用方必须据此降级。"""


def get_config():
    return {
        "base_url": os.environ.get(ENV_BASE_URL, "").strip(),
        "api_key": os.environ.get(ENV_API_KEY, "").strip(),
        "model": os.environ.get(ENV_MODEL, "").strip(),
    }


def is_enabled() -> bool:
    cfg = get_config()
    return bool(cfg["base_url"] and cfg["api_key"] and cfg["model"])


def chat(messages, *, timeout: float = 60.0, max_retries: int = 2,
         max_tokens: int = 2048) -> str:
    """OpenAI 兼容对话补全 → 助手回复文本；失败抛 LLMError（有限重试后）。"""
    if not is_enabled():
        raise LLMError(
            "LLM 未配置（BIDCHECKER_LLM_BASE_URL/API_KEY/MODEL），"
            "规则通路不受影响；配置方法见 plan/03-架构与技术选型.md §四")
    cfg = get_config()
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": list(messages),
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "stream": False,
        "enable_thinking": False,  # qwen3 系：关闭思考态提速（兼容不含此键的服务端）
    }
    last_exc: Exception = LLMError("未发起请求")
    for attempt in range(max_retries + 1):
        try:
            request = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {cfg['api_key']}"})
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return _clean_content(body["choices"][0]["message"]["content"])
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001 —— 网络/协议错误统一重试
            last_exc = LLMError(f"LLM 调用失败：{exc.__class__.__name__}: {exc}")
            if attempt < max_retries:
                time.sleep(min(1.0, 0.5 * (attempt + 1)))
    raise last_exc


def _clean_content(content: str) -> str:
    """剥离 <think> 块与代码围栏；截断 JSON 做最小修复；不合法 → LLMError。"""
    text = (content or "").strip()
    while "<think>" in text:
        start = text.index("<think>")
        end = text.find("</think>", start)
        text = (text[:start] + (text[end + len("</think>"):] if end >= 0 else "")).strip()
    if text.startswith("```"):
        first_line_end = text.find("\n")
        text = text[first_line_end + 1:] if first_line_end >= 0 else ""
        end = text.rfind("```")
        text = text[:end].strip() if end >= 0 else text.strip()
    stripped = text.strip()
    if stripped[:1] in ("{", "["):
        return stripped
    for opener in ("{", "["):
        idx = stripped.find(opener)
        if idx >= 0:
            candidate = stripped[idx:]
            try:
                json.loads(candidate)
                return candidate
            except ValueError:
                continue
    if not stripped:
        raise LLMError("LLM 返回空内容")
    return stripped  # 纯文本回复（非 JSON 形态）原样交由调用方校验


__all__ = ["ENV_BASE_URL", "ENV_API_KEY", "ENV_MODEL", "LLMError",
           "get_config", "is_enabled", "chat"]
