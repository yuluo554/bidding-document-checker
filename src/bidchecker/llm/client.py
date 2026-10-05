"""LLM 客户端：OpenAI 兼容 /chat/completions，配置全部走环境变量（决策 D8）。

未配置环境变量 → LLM 功能整体禁用，规则通路不受影响；客户端必配
enable_thinking=false（qwen3 系提速）、max_tokens 截断 JSON 修复、超时+有限重试。
M4 交付。
"""
import os

ENV_BASE_URL = "BIDCHECKER_LLM_BASE_URL"
ENV_API_KEY = "BIDCHECKER_LLM_API_KEY"
ENV_MODEL = "BIDCHECKER_LLM_MODEL"


def get_config():
    return {
        "base_url": os.environ.get(ENV_BASE_URL, "").strip(),
        "api_key": os.environ.get(ENV_API_KEY, "").strip(),
        "model": os.environ.get(ENV_MODEL, "").strip(),
    }


def is_enabled() -> bool:
    cfg = get_config()
    return bool(cfg["base_url"] and cfg["api_key"] and cfg["model"])


def chat(messages, *, timeout: float = 60.0, max_retries: int = 2):
    """OpenAI 兼容对话补全。摘录类输出必须过"原文子串"校验后才能进入参数卡。"""
    if not is_enabled():
        raise RuntimeError(
            "LLM 未配置（BIDCHECKER_LLM_BASE_URL/API_KEY/MODEL），"
            "规则通路不受影响；配置方法见 plan/03-架构与技术选型.md §四"
        )
    raise NotImplementedError("LLM 客户端计划于 M4 交付（plan/05 M4）")
