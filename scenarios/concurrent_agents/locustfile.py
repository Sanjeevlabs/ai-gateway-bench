from __future__ import annotations

import os

import httpx
from locust import HttpUser, between, task

from common.payloads import anthropic_body, openai_body
from common.sse import stream_request


class ConcurrentAgentUser(HttpUser):
    wait_time = between(0.05, 0.15)
    host = os.getenv("GWBENCH_TARGET", "http://127.0.0.1:8000")
    endpoint = os.getenv("GWBENCH_ENDPOINT", "/v1/messages")

    def on_start(self) -> None:
        self.client_http = httpx.Client(timeout=180)

    @task
    def agent_turn(self) -> None:
        stream_request(
            self.client_http,
            f"{self.host}{self.endpoint}",
            (
                openai_body()
                if os.getenv("GWBENCH_PROTOCOL", "anthropic") == "openai"
                else anthropic_body()
            ),
            name="concurrent_agents",
            environment=self.environment,
            headers={"Authorization": f"Bearer {os.getenv('GWBENCH_API_KEY', 'gwbench')}"},
        )
