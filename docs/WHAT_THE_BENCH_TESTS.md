# What GatewayBench tests (agentic-coding focus)

GatewayBench measures **gateway overhead**, not model quality. Every number is the cost the gateway adds on top of the upstream, isolated against a local deterministic mock:

```
overhead = latency(client -> gateway -> mock) - latency(client -> mock directly)
```

The lens is a **coding agent**, not a chatbot. A coding agent is a tight loop: read files, stream a plan, emit tool calls, apply edits, repeat. It issues many turns per task, streams every turn, leans hard on tool calls, and ships large context (open files, diffs, repo maps). So the metrics that matter are the ones an agent hits thousands of times per session, where a few milliseconds of gateway overhead compounds into seconds of wall-clock lag a developer actually feels.

Gateways under test: LiteLLM (Rust), LiteLLM (Python v1), Portkey (OSS gateway), Bifrost.

## Scenarios, and the agent behavior each one stands in for

| Test folder | Agent behavior it models | What it drives |
|---|---|---|
| `ttft/` | The agent starts a turn; the developer waits for the first token | Streaming request, measure added time to first chunk |
| `inter-chunk-latency/` | The agent streams a long edit or explanation | Streaming, measure added gap between every SSE chunk (p50/p99/max + jitter) |
| `chunk-fidelity/` | The editor renders tokens as they arrive | Compare downstream chunk count/boundaries to the mock's |
| `tool-call-latency/` | The agent decides to call a tool (edit_file, run_test) | Streamed `tool_calls` with argument deltas; measure added latency and reassembly correctness |
| `large-prompt/` | The agent pastes files / repo context | 1k / 10k / 100k token prompts; measure how overhead scales with size |
| `throughput/` | A team of agents (or parallel subtasks) hits one gateway | Rising req/s until the latency knee or errors |
| `tail-latency/` | The unlucky turn during a busy period | p99 / p99.9 added latency under concurrency |

## Metrics that matter for agents

Standard-but-critical: TTFT overhead, time-to-last-token overhead, throughput ceiling, peak RSS + CPU (cost per 1M requests), and error rate under load. These decide perceived speed and operating cost, and they are table stakes for any serious comparison.

## Interesting metrics, and why they are interesting

These are the metrics most benchmarks skip, and they are exactly the ones that separate a gateway that "works in a demo" from one that holds up inside an agent loop.

**Inter-chunk jitter under concurrent load.** Not mean inter-chunk latency, but its p99 and standard deviation while the gateway is busy. An agent's stream should arrive as a smooth trickle; a gateway that stalls for 40ms every few chunks makes the editor stutter even when its average looks fine. This is interesting because it is invisible to any average-latency benchmark and it is where runtime architecture leaks through: a garbage-collected or single-threaded event loop shows periodic jitter spikes under load that a mean hides.

**Chunk fidelity (re-chunking / coalescing).** Does the gateway forward SSE chunks 1:1, or does it buffer and re-emit? A gateway that coalesces the stream, even partially, destroys the token-by-token feel an agent UI depends on, and in the worst case buffers the whole response then flushes it once (TTFT looks fine, but the stream arrives as one late burst). We measure this directly as the ratio of downstream to upstream chunks plus boundary alignment, which most benchmarks never look at because they only time first and last byte.

**Tool-call argument-delta integrity.** Under streaming, tool-call arguments arrive as partial JSON fragments across many chunks. The gateway must forward them so the client can reassemble valid JSON, in order, with nothing dropped, duplicated, or reordered. This is interesting because it is a correctness metric hiding inside a performance benchmark: a gateway can be fast and still silently corrupt a tool call under load, which for a coding agent means a broken edit rather than a slow one.

**Overhead slope vs prompt size.** Overhead at 1k tokens tells you little; the slope from 1k to 100k tells you whether the gateway re-parses and re-serializes the whole payload on the hot path. Agents routinely send 50k-plus token contexts, so a gateway with a steep slope is fine for chat and painful for coding.

## The moat metric: sustained flat-tail streaming under concurrency

If we highlight one number that is structurally hard for competitors to match, it is **p99 inter-chunk latency held flat as concurrency rises** (paired with chunk fidelity staying 1:1). It combines three things a gateway cannot fake: no output buffering, no per-request re-serialization on the stream path, and no runtime pauses under load.

This is structurally harder for the other architectures, not just a tuning gap:

- A **Python** proxy pays the GIL and per-chunk Python-object overhead on every SSE frame; under concurrency the tail widens because streaming work across requests contends on one interpreter.
- **Go** (Bifrost) is fast but garbage-collected, so sustained high-throughput streaming shows periodic GC-driven jitter in the p99 inter-chunk gap even when the mean is excellent.
- **Node** (Portkey OSS) rides a single-threaded event loop; a burst of concurrent streams plus JSON work per chunk periodically delays the loop, which surfaces as inter-chunk stalls.

A **Rust** streaming path with no buffering and no GC can keep the p99 inter-chunk gap nearly flat as concurrency climbs. That is the differentiated claim worth measuring honestly and publishing: not "we're a bit faster on average," but "our tail stays flat where the runtime of every alternative structurally makes theirs wobble." It is also the metric a competitor cannot close by turning a knob, because it follows from the runtime they are built on.

Note on honesty: this is the hypothesis the bench is designed to test, not a result. The published chart will show whatever the measurements show, with versions, configs, and hardware disclosed, and the mock and driver held identical across all four gateways.
