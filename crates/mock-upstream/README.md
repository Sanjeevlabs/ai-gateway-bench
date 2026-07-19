# Rust mock upstream

This is the high-concurrency replacement for `mock/app.py`. It exposes the
same routes and environment knobs:

```text
GET  /health
POST /v1/messages
POST /v1/chat/completions

MOCK_TTFT_MS       default 20
MOCK_ITL_MS        default 5
MOCK_OUTPUT_TOKENS default 40
MOCK_FAIL_STATUS   default disabled
MOCK_HOST          default 127.0.0.1
MOCK_PORT          default 9000
```

Run it from the repository root:

```bash
cargo run --release -p mock-upstream
```

The streaming responses are deterministic SSE sequences. Anthropic requests
with `tools` or `_gwbench_tool: true` return the fixed `tool_use` response and
partial JSON argument deltas used by the agent replay tests.
