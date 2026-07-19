from __future__ import annotations

import os

import httpx
from locust import HttpUser, between, task

from common.payloads import anthropic_body, openai_body
from common.sse import stream_request


class StreamingTurnUser(HttpUser):
    wait_time = between(0.1, 0.3)
    host = os.getenv("GWBENCH_TARGET", "http://127.0.0.1:8000")
    endpoint = os.getenv("GWBENCH_ENDPOINT", "/v1/messages")

    def on_start(self) -> None:
        self.client_http = httpx.Client(timeout=120)

    @task
    def streamed_turn(self) -> None:
        stream_request(
            self.client_http,
            f"{self.host}{self.endpoint}",
            (
                openai_body()
                if os.getenv("GWBENCH_PROTOCOL", "anthropic") == "openai"
                else anthropic_body()
            ),
            name="streaming_turn",
            environment=self.environment,
            headers={"Authorization": f"Bearer {os.getenv('GWBENCH_API_KEY', 'gwbench')}"},
        )
