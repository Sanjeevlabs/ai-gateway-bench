from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import httpx
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.metrics import percentile, write_result
from common.payloads import anthropic_body, openai_body
from common.sse import stream_request


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--endpoint", choices=("anthropic", "openai"), required=True)
    parser.add_argument("--model", default="mock")
    parser.add_argument("--output", required=True)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--header", action="append", default=[])
    parser.add_argument("--pid", type=int)
    parser.add_argument("--expected-chunks", type=int)
    args = parser.parse_args()

    body_factory = anthropic_body if args.endpoint == "anthropic" else openai_body
    headers = {"Authorization": f"Bearer {args.api_key}"} if args.api_key else {}
    for header in args.header:
        name, separator, value = header.partition(":")
        if not separator or not name.strip():
            parser.error(f"invalid --header value: {header!r}")
        headers[name.strip()] = value.strip()
    latencies: list[float] = []
    ttft: list[float] = []
    gaps: list[float] = []
    fidelity: list[float] = []
    errors: list[str] = []
    rss: list[int] = []
    process = psutil.Process(args.pid) if args.pid else None

    with httpx.Client(timeout=180) as client:
        for _ in range(args.count):
            started = time.perf_counter()
            if args.stream:
                metrics = stream_request(
                    client,
                    args.url,
                    body_factory(model=args.model),
                    name=args.label,
                    headers=headers,
                )
                elapsed = (time.perf_counter() - started) * 1000
                if metrics.ttft_ms is not None:
                    ttft.append(metrics.ttft_ms)
                gaps.extend(metrics.inter_chunk_ms)
                if args.expected_chunks:
                    fidelity.append(metrics.chunk_count / args.expected_chunks)
                if metrics.status_code >= 400 or metrics.error:
                    errors.append(metrics.error or f"HTTP {metrics.status_code}")
            else:
                response = client.post(
                    args.url,
                    json=body_factory(model=args.model, stream=False),
                    headers=headers,
                )
                elapsed = (time.perf_counter() - started) * 1000
                if response.is_error:
                    errors.append(f"HTTP {response.status_code}: {response.text[:200]}")
            latencies.append(elapsed)
            if process:
                try:
                    rss.append(process.memory_info().rss)
                except psutil.Error:
                    pass

    result = {
        "label": args.label,
        "endpoint": args.url,
        "count": args.count,
        "streaming": args.stream,
        "latency_p50_ms": percentile(latencies, 0.50),
        "latency_p99_ms": percentile(latencies, 0.99),
        "ttft_ms": {
            "p50": percentile(ttft, 0.50),
            "p99": percentile(ttft, 0.99),
        },
        "inter_chunk_ms": {
            "p50": percentile(gaps, 0.50),
            "p99": percentile(gaps, 0.99),
        },
        "chunk_fidelity": statistics.mean(fidelity) if fidelity else None,
        "peak_rss_mb": round(max(rss) / 1_000_000, 3) if rss else None,
        "errors": errors,
    }
    write_result(args.output, result)
    print(result)


if __name__ == "__main__":
    main()
