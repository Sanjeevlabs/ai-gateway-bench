from __future__ import annotations

import argparse
import statistics
import time

import httpx


def run(url: str, count: int) -> list[float]:
    body = {"model": "mock", "messages": [{"role": "user", "content": "x"}]}
    values = []
    with httpx.Client(timeout=30) as client:
        for _ in range(count):
            started = time.perf_counter()
            client.post(url, json=body)
            values.append((time.perf_counter() - started) * 1000)
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--happy-url", default="http://127.0.0.1:8000/v1/chat/completions")
    parser.add_argument("--fail-url")
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()
    happy = run(args.happy_url, args.count)
    result = {
        "count": args.count,
        "happy_mean_ms": round(statistics.mean(happy), 3),
        "happy_p99_ms": round(sorted(happy)[-1], 3),
    }
    if args.fail_url:
        failed = run(args.fail_url, args.count)
        result.update(
            {
                "fail_mean_ms": round(statistics.mean(failed), 3),
                "fail_p99_ms": round(sorted(failed)[-1], 3),
                "added_mean_ms": round(statistics.mean(failed) - statistics.mean(happy), 3),
                "added_p99_ms": round(sorted(failed)[-1] - sorted(happy)[-1], 3),
            }
        )
    print(result)


if __name__ == "__main__":
    main()
