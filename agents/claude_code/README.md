# Claude Code session replay

This deterministic 30-turn profile models repository inspection, focused edits,
testing, and review. Twelve turns include streamed tool-call argument deltas;
context grows from 256 to 21,504 synthetic tokens. The runner sends a fixed
system prompt and tool schema, appends each canned tool result to the
conversation, and replays the accumulated history. The local mock returns the
fixed Anthropic text/tool sequence; no real model is involved.

It is replayed over Anthropic `/v1/messages` for every gateway. Rust's current
route is non-streaming, so its session result uses the same deterministic loop
with non-streaming requests and a matching direct baseline.
