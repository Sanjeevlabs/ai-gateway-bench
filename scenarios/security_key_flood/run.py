from __future__ import annotations

import argparse
import asyncio
import time
from collections import Counter

import httpx


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/messages")
    parser.add_argument("--requests", type=int, default=500)
    args = parser.parse_args()
    body = {"model": "mock", "max_tokens": 1, "messages": [{"role": "user", "content": "x"}]}

    async with httpx.AsyncClient(timeout=10) as client:
        started = time.perf_counter()

        async def send(index: int) -> int:
            response = await client.post(
                args.url,
                headers={"Authorization": f"Bearer invalid-{index}"},
                json=body,
            )
            return response.status_code

        statuses = await asyncio.gather(*(send(index) for index in range(args.requests)))
    elapsed = time.perf_counter() - started
    rejected = sum(status in (401, 403) for status in statuses)
    result = {
        "requests": len(statuses),
        "rejected_at_edge": rejected,
        "status_counts": dict(Counter(statuses)),
        "elapsed_s": round(elapsed, 3),
    }
    print(result)
    if rejected != len(statuses):
        raise SystemExit("not all invalid keys received 401/403")


if __name__ == "__main__":
    asyncio.run(main())
