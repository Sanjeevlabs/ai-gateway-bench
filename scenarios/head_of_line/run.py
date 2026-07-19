from __future__ import annotations

import argparse
import asyncio
import time

import httpx


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/messages")
    args = parser.parse_args()
    headers = {"Authorization": "Bearer gwbench"}

    async with httpx.AsyncClient(timeout=180) as client:
        async def request(tokens: int) -> float:
            body = {
                "model": "mock",
                "max_tokens": 40,
                "stream": True,
                "messages": [{"role": "user", "content": "token " * tokens}],
            }
            started = time.perf_counter()
            response = await client.post(args.url, headers=headers, json=body)
            response.raise_for_status()
            return (time.perf_counter() - started) * 1000

        small = await asyncio.gather(*(request(32) for _ in range(10)))
        large = await request(100_000)
    print({"small_p99_ms": round(sorted(small)[-1], 3), "large_ms": round(large, 3)})


if __name__ == "__main__":
    asyncio.run(main())
