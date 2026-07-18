"""Deterministic OpenAI + Anthropic mock upstream for AIGatewayBench.

The mock is the fixed zero point every gateway is measured against: it removes
real provider latency and variance so what remains is gateway overhead. Timing
is configurable so streaming looks realistic without real-world noise:

    MOCK_TTFT_MS         delay before the first streamed chunk   (default 20)
    MOCK_ITL_MS          delay between streamed chunks           (default 5)
    MOCK_OUTPUT_TOKENS   number of streamed text chunks          (default 40)

Endpoints:
    POST /v1/messages            Anthropic Messages (stream + non-stream, text + tool_use)
    POST /v1/chat/completions    OpenAI Chat Completions (stream + non-stream)
    GET  /health
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()

TTFT_S = float(os.environ.get("MOCK_TTFT_MS", "20")) / 1000.0
ITL_S = float(os.environ.get("MOCK_ITL_MS", "5")) / 1000.0
OUTPUT_TOKENS = int(os.environ.get("MOCK_OUTPUT_TOKENS", "40"))

_WORD = "token "


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _wants_tool_call(body: dict) -> bool:
    return bool(body.get("tools")) or body.get("_gwbench_tool") is True


# ---------------------------------------------------------------- Anthropic


def _anthropic_body() -> dict:
    return {
        "id": "msg_gwbench",
        "type": "message",
        "role": "assistant",
        "model": "mock-upstream",
        "content": [{"type": "text", "text": _WORD * OUTPUT_TOKENS}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": OUTPUT_TOKENS},
    }


async def _anthropic_stream(tool_call: bool) -> AsyncIterator[bytes]:
    def event(kind: str, payload: dict) -> bytes:
        return f"event: {kind}\ndata: {json.dumps(payload)}\n\n".encode()

    yield event("message_start", {"type": "message_start", "message": _anthropic_body() | {"content": []}})
    await asyncio.sleep(TTFT_S)

    if tool_call:
        yield event("content_block_start", {"type": "content_block_start", "index": 0,
                    "content_block": {"type": "tool_use", "id": "toolu_gwbench", "name": "edit_file", "input": {}}})
        # Stream the JSON arguments as partial deltas, the way a real tool call arrives.
        fragments = ['{"path":', ' "src/main', '.rs", "content":', ' "fn main', '() {}"}']
        for fragment in fragments:
            await asyncio.sleep(ITL_S)
            yield event("content_block_delta", {"type": "content_block_delta", "index": 0,
                        "delta": {"type": "input_json_delta", "partial_json": fragment}})
        yield event("content_block_stop", {"type": "content_block_stop", "index": 0})
    else:
        yield event("content_block_start", {"type": "content_block_start", "index": 0,
                    "content_block": {"type": "text", "text": ""}})
        for _ in range(OUTPUT_TOKENS):
            await asyncio.sleep(ITL_S)
            yield event("content_block_delta", {"type": "content_block_delta", "index": 0,
                        "delta": {"type": "text_delta", "text": _WORD}})
        yield event("content_block_stop", {"type": "content_block_stop", "index": 0})

    yield event("message_delta", {"type": "message_delta",
                "delta": {"stop_reason": "tool_use" if tool_call else "end_turn"},
                "usage": {"output_tokens": OUTPUT_TOKENS}})
    yield event("message_stop", {"type": "message_stop"})


@app.post("/v1/messages")
async def messages(request: Request):
    body = await request.json()
    if body.get("stream"):
        return StreamingResponse(_anthropic_stream(_wants_tool_call(body)), media_type="text/event-stream")
    await asyncio.sleep(TTFT_S)
    return JSONResponse(_anthropic_body())


# ------------------------------------------------------------------- OpenAI


def _openai_body() -> dict:
    return {
        "id": "chatcmpl-gwbench",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "mock-upstream",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": _WORD * OUTPUT_TOKENS},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": OUTPUT_TOKENS, "total_tokens": OUTPUT_TOKENS + 1},
    }


async def _openai_stream() -> AsyncIterator[bytes]:
    def chunk(delta: dict, finish: str | None = None) -> bytes:
        payload = {
            "id": "chatcmpl-gwbench",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "mock-upstream",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        return f"data: {json.dumps(payload)}\n\n".encode()

    await asyncio.sleep(TTFT_S)
    yield chunk({"role": "assistant", "content": ""})
    for _ in range(OUTPUT_TOKENS):
        await asyncio.sleep(ITL_S)
        yield chunk({"content": _WORD})
    yield chunk({}, finish="stop")
    yield b"data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    if body.get("stream"):
        return StreamingResponse(_openai_stream(), media_type="text/event-stream")
    await asyncio.sleep(TTFT_S)
    return JSONResponse(_openai_body())
