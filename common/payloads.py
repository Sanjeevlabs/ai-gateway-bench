from __future__ import annotations


def anthropic_body(
    *,
    model: str = "mock",
    prompt_tokens: int = 32,
    stream: bool = True,
    tool: bool = False,
) -> dict:
    return {
        "model": model,
        "max_tokens": 40,
        "stream": stream,
        "messages": [{"role": "user", "content": "token " * prompt_tokens}],
        **({"_gwbench_tool": True} if tool else {}),
    }


def openai_body(
    *,
    model: str = "mock",
    prompt_tokens: int = 32,
    stream: bool = True,
) -> dict:
    return {
        "model": model,
        "stream": stream,
        "messages": [{"role": "user", "content": "token " * prompt_tokens}],
    }
