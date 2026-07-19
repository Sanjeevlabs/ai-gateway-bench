from __future__ import annotations

import json
import os

import httpx
from locust import HttpUser, between, task

from common.metrics import summary
from common.payloads import anthropic_body
from common.sse import stream_request


class ToolCallLoopUser(HttpUser):
    wait_time = between(0.1, 0.3)
    host = os.getenv("GWBENCH_TARGET", "http://127.0.0.1:8000")

    def on_start(self) -> None:
        self.client_http = httpx.Client(timeout=120)

    @task
    def streamed_tool_call(self) -> None:
        metrics = stream_request(
            self.client_http,
            f"{self.host}/v1/messages",
            anthropic_body(tool=True),
            name="tool_call_loop",
            environment=self.environment,
            headers={"Authorization": f"Bearer {os.getenv('GWBENCH_API_KEY', 'gwbench')}"},
        )
        fragments = [
            event["delta"]["partial_json"]
            for kind, event in metrics.raw_events
            if kind == "content_block_delta"
            and isinstance(event, dict)
            and event.get("delta", {}).get("type") == "input_json_delta"
        ]
        try:
            parsed = json.loads("".join(fragments))
            if list(parsed) != ["path", "content"]:
                raise ValueError("tool argument order changed")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.environment.events.request.fire(
                request_type="STREAM",
                name="tool_call_loop/correctness",
                response_time=0,
                response_length=0,
                exception=exc,
            )
        else:
            self.environment.events.request.fire(
                request_type="STREAM",
                name="tool_call_loop/correctness",
                response_time=0,
                response_length=0,
                exception=None,
            )
