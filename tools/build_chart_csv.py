from __future__ import annotations

import csv
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"


def write(name: str, rows: list[dict[str, object]]) -> None:
    path = RESULTS / name
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def session() -> None:
    data = json.loads((RESULTS / "session_overhead.json").read_text())
    write(
        "session_overhead.csv",
        [
            {
                "gateway": gateway,
                "claude_code_added_seconds": values["claude_code"]["added_seconds"],
                "codex_added_seconds": values["codex"]["added_seconds"],
            }
            for gateway, values in data.items()
        ],
    )


def concurrency() -> None:
    prefixes = {
        "litellm-rust": "litellm_rust_messages",
        "litellm-python": "litellm_python_messages",
        "bifrost": "bifrost_messages",
        "portkey": "portkey_messages",
    }
    data = []
    for concurrency in (1, 4, 8, 16):
        baseline = json.loads((RESULTS / f"direct_messages_c{concurrency}.json").read_text())
        for gateway, prefix in prefixes.items():
            result = json.loads((RESULTS / f"{prefix}_c{concurrency}.json").read_text())
            data.append(
                {
                    "gateway": gateway,
                    "concurrency": concurrency,
                    "p99_overhead_ms": result["latency_p99_ms"] - baseline["latency_p99_ms"],
                    "gateway_p99_ms": result["latency_p99_ms"],
                    "baseline_p99_ms": baseline["latency_p99_ms"],
                }
            )
    (RESULTS / "concurrency_sweep.json").write_text(json.dumps(data, indent=2) + "\n")
    write(
        "latency_vs_concurrency.csv",
        [
            {
                "gateway": row["gateway"],
                "concurrency": row["concurrency"],
                "p99_added_latency_ms": row["p99_overhead_ms"],
            }
            for row in data
        ],
    )


def ttft() -> None:
    data = json.loads((RESULTS / "ttft_overhead.json").read_text())
    write(
        "ttft_overhead.csv",
        [
            {
                "gateway": gateway,
                "available": values["available"],
                "p50_added_ttft_ms": values["p50_overhead_ms"] or "",
                "p99_added_ttft_ms": values["p99_overhead_ms"] or "",
            }
            for gateway, values in data.items()
        ],
    )


def cost() -> None:
    data = json.loads((RESULTS / "cost_per_million.json").read_text())
    write(
        "cost_per_million.csv",
        [
            {
                "gateway": gateway,
                "dollars_per_million": values["dollars_per_million"],
            }
            for gateway, values in data.items()
        ],
    )


def overhead() -> None:
    data = json.loads((RESULTS / "overhead_summary.json").read_text())
    rss_files = {
        "litellm-rust": "mem_litellm_rust_release.txt",
        "litellm-python": "mem_litellm_python_messages.txt",
        "bifrost": "mem_bifrost_messages.txt",
        "portkey": "mem_portkey_messages.txt",
    }
    rows = []
    for row in data:
        peak = next(
            float(line.split("=", 1)[1])
            for line in (RESULTS / rss_files[row["gateway"]]).read_text().splitlines()
            if line.startswith("peak_rss_mb=")
        )
        rows.append(
            {
                "gateway": row["gateway"],
                "p99_added_latency_ms": row["latency_p99_overhead_ms"],
                "peak_rss_mb": peak,
            }
        )
    write("overhead_comparison.csv", rows)


if __name__ == "__main__":
    session()
    concurrency()
    ttft()
    cost()
    overhead()
