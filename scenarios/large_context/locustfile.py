from __future__ import annotations

import os

import httpx
from locust import HttpUser, between, task

from common.payloads import anthropic_body, openai_body
from common.sse import stream_request


class LargeContextUser(HttpUser):
    wait_time = between(0.2, 0.4)
    host = os.getenv("GWBENCH_TARGET", "http://127.0.0.1:8000")
    endpoint = os.getenv("GWBENCH_ENDPOINT", "/v1/messages")
    sizes = (1_000, 10_000, 100_000)

    def on_start(self) -> None:
        self.client_http = httpx.Client(timeout=180)
        self.index = 0

    @task
    def large_context_turn(self) -> None:
        size = self.sizes[self.index % len(self.sizes)]
        self.index += 1
        stream_request(
            self.client_http,
            f"{self.host}{self.endpoint}",
            (
                openai_body(prompt_tokens=size)
                if os.getenv("GWBENCH_PROTOCOL", "anthropic") == "openai"
                else anthropic_body(prompt_tokens=size)
            ),
            name=f"large_context/{size}",
            environment=self.environment,
            headers={"Authorization": f"Bearer {os.getenv('GWBENCH_API_KEY', 'gwbench')}"},
        )
