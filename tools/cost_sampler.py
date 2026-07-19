from __future__ import annotations

import argparse
import csv
import time

import psutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("--output", required=True)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--interval", type=float, default=0.25)
    args = parser.parse_args()
    process = psutil.Process(args.pid)
    process.cpu_percent(None)
    started = time.monotonic()
    rows: list[dict[str, float]] = []
    while time.monotonic() - started < args.duration:
        try:
            rows.append(
                {
                    "elapsed_s": time.monotonic() - started,
                    "cpu_percent": process.cpu_percent(None),
                    "rss_mb": process.memory_info().rss / 1_000_000,
                }
            )
        except psutil.Error:
            break
        time.sleep(args.interval)
    with open(args.output, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=("elapsed_s", "cpu_percent", "rss_mb"))
        writer.writeheader()
        writer.writerows(rows)
    avg_cpu = sum(row["cpu_percent"] for row in rows) / len(rows) if rows else 0
    peak_rss = max((row["rss_mb"] for row in rows), default=0)
    print({"samples": len(rows), "avg_cpu_percent": round(avg_cpu, 3), "peak_rss_mb": round(peak_rss, 3)})


if __name__ == "__main__":
    main()
