# Codex-style session replay

This deterministic 30-turn profile emphasizes repository search, compile/test
loops, and implementation tool calls. Seventeen turns include streamed
tool-call argument deltas; context grows from 512 to 25,600 synthetic tokens.
The runner sends a fixed system prompt and tool schema, appends each canned
tool result to the conversation, and replays the accumulated history. The
local mock returns the fixed Anthropic text/tool sequence; no real model is
involved. “Codex-style” describes only this turn mix: it is replayed over
Anthropic `/v1/messages` for apples-to-apples gateway comparison. Rust's
current route is non-streaming, so its result uses matching non-streaming
requests and a direct baseline.
