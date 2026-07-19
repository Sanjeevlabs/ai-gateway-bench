from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class StreamMetrics:
    status_code: int
    ttft_ms: float | None
    inter_chunk_ms: list[float] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    raw_events: list[tuple[str | None, dict[str, Any] | str]] = field(default_factory=list)
    error: str | None = None

    @property
    def chunk_count(self) -> int:
        return len(self.raw_events)


def _parse_event(block: str) -> tuple[str | None, dict[str, Any] | str] | None:
    event_name = None
    data_lines: list[str] = []
    for line in block.splitlines():
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not data_lines:
        return None
    data = "\n".join(data_lines)
    if data == "[DONE]":
        return event_name, data
    try:
        return event_name, json.loads(data)
    except json.JSONDecodeError:
        return event_name, data


def _fire(environment: Any, name: str, started: float, error: Exception | None = None) -> None:
    if environment is None:
        return
    environment.events.request.fire(
        request_type="STREAM",
        name=name,
        response_time=(time.perf_counter() - started) * 1000,
        response_length=0,
        exception=error,
    )


def stream_request(
    client: httpx.Client,
    url: str,
    body: dict[str, Any],
    *,
    name: str,
    environment: Any = None,
    headers: dict[str, str] | None = None,
) -> StreamMetrics:
    started = time.perf_counter()
    metrics = StreamMetrics(status_code=0, ttft_ms=None)
    try:
        with client.stream("POST", url, json=body, headers=headers) as response:
            metrics.status_code = response.status_code
            block = bytearray()
            previous = None
            for piece in response.iter_bytes():
                block.extend(piece)
                while b"\n\n" in block:
                    raw, _, remainder = block.partition(b"\n\n")
                    block = bytearray(remainder)
                    parsed = _parse_event(raw.decode("utf-8", errors="replace"))
                    if parsed is None:
                        continue
                    now = time.perf_counter()
                    if metrics.ttft_ms is None:
                        metrics.ttft_ms = (now - started) * 1000
                        _fire(environment, f"{name}/ttft", started)
                    elif previous is not None:
                        gap_started = previous
                        _fire(environment, f"{name}/inter_chunk", gap_started)
                        metrics.inter_chunk_ms.append((now - previous) * 1000)
                    previous = now
                    metrics.raw_events.append(parsed)
                    if isinstance(parsed[1], dict):
                        metrics.chunks.append(parsed[1])
            if block:
                parsed = _parse_event(block.decode("utf-8", errors="replace"))
                if parsed is not None:
                    metrics.raw_events.append(parsed)
            if response.is_error:
                metrics.error = f"HTTP {response.status_code}"
    except Exception as exc:
        metrics.error = str(exc)
        _fire(environment, name, started, exc)
    return metrics
