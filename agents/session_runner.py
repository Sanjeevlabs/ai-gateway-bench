from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.sse import stream_request


def _body(
    turn: dict[str, Any],
    model: str,
    stream: bool,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    context = "file-context " * turn["context_tokens"]
    prompt = turn["prompt"] + "\n" + context
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": 40,
        "stream": stream,
        "messages": [*messages, {"role": "user", "content": prompt}],
    }
    if turn["tool"]:
        body["tools"] = [
            {
                "name": "edit_file",
                "description": "Edit a repository file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            }
        ]
    return body


def _tool_json_valid(metrics: Any) -> bool:
    fragments: list[str] = []
    for event_name, payload in metrics.raw_events:
        if event_name != "content_block_delta" or not isinstance(payload, dict):
            continue
        delta = payload.get("delta", {})
        if delta.get("type") == "input_json_delta":
            fragments.append(delta.get("partial_json", ""))
    if not fragments:
        return False
    try:
        value = json.loads("".join(fragments))
    except json.JSONDecodeError:
        return False
    return isinstance(value, dict) and list(value) == ["path", "content"]


def _tool_input(metrics: Any) -> dict[str, str]:
    fragments: list[str] = []
    for event_name, payload in metrics.raw_events:
        if event_name != "content_block_delta" or not isinstance(payload, dict):
            continue
        delta = payload.get("delta", {})
        if delta.get("type") == "input_json_delta":
            fragments.append(delta.get("partial_json", ""))
    try:
        value = json.loads("".join(fragments))
    except json.JSONDecodeError:
        value = {"path": "src/main.rs", "content": "fn main() {}"}
    return value


def replay(
    *,
    label: str,
    url: str,
    model: str,
    turns: list[dict[str, Any]],
    headers: dict[str, str],
    stream: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    turn_results: list[dict[str, Any]] = []
    errors: list[str] = []
    invalid_tool_turns: list[int] = []
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": "You are a deterministic coding agent. Follow the registered tools."}
    ]
    with httpx.Client(timeout=180) as client:
        for turn in turns:
            turn_started = time.perf_counter()
            metrics = stream_request(
                client,
                url,
                _body(turn, model, stream, messages),
                name=f"{label}/turn-{turn['index']}",
                headers=headers,
            )
            elapsed = (time.perf_counter() - turn_started) * 1000
            error = metrics.error or (
                f"HTTP {metrics.status_code}" if metrics.status_code >= 400 else None
            )
            if error:
                errors.append(f"turn {turn['index']}: {error}")
            if stream and turn["tool"] and not _tool_json_valid(metrics):
                invalid_tool_turns.append(turn["index"])
            if turn["tool"]:
                tool_input = _tool_input(metrics) if stream else {
                    "path": "src/main.rs",
                    "content": "fn main() {}",
                }
                messages.extend(
                    [
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": f"toolu_gwbench_{turn['index']}",
                                    "name": "edit_file",
                                    "input": tool_input,
                                }
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": f"toolu_gwbench_{turn['index']}",
                                    "content": "ok: deterministic file updated",
                                }
                            ],
                        },
                    ]
                )
            else:
                messages.append(
                    {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "completed deterministic turn"}],
                    }
                )
            turn_results.append(
                {
                    "index": turn["index"],
                    "tool": turn["tool"],
                    "context_tokens": turn["context_tokens"],
                    "latency_ms": round(elapsed, 3),
                    "ttft_ms": metrics.ttft_ms,
                    "inter_chunk_p99_ms": (
                        max(metrics.inter_chunk_ms) if metrics.inter_chunk_ms else None
                    ),
                    "errors": [error] if error else [],
                }
            )
    return {
        "label": label,
        "endpoint": url,
        "turn_count": len(turns),
        "total_wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
        "turns": turn_results,
        "invalid_tool_turns": invalid_tool_turns,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", default="anthropic/mock")
    parser.add_argument("--output", required=True)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--header", action="append", default=[])
    parser.add_argument("--non-stream", action="store_true")
    args = parser.parse_args()
    module_name = f"agents.{args.profile}.profile"
    profile = __import__(module_name, fromlist=["TURNS"])
    headers = {"Authorization": f"Bearer {args.api_key}"} if args.api_key else {}
    for header in args.header:
        name, separator, value = header.partition(":")
        if not separator or not name.strip():
            parser.error(f"invalid --header value: {header!r}")
        headers[name.strip()] = value.strip()
    result = replay(
        label=f"{args.profile}:{args.url}",
        url=args.url,
        model=args.model,
        turns=profile.TURNS,
        headers=headers,
        stream=not args.non_stream,
    )
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(result)


if __name__ == "__main__":
    main()
