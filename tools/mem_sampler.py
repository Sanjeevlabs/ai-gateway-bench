from __future__ import annotations

import argparse
import csv
import time

import psutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("--output", default="results/memory.csv")
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--duration", type=float, default=60)
    args = parser.parse_args()

    process = psutil.Process(args.pid)
    started = time.time()
    samples: list[tuple[float, int]] = []
    while time.time() - started < args.duration:
        try:
            samples.append((time.time(), process.memory_info().rss))
        except psutil.Error:
            break
        time.sleep(args.interval)
    with open(args.output, "w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["timestamp", "rss_bytes"])
        writer.writerows(samples)
    if samples:
        rss = [value for _, value in samples]
        duration = samples[-1][0] - samples[0][0] or 1
        slope = (rss[-1] - rss[0]) / duration
        print(f"idle_rss_mb={rss[0] / 1_000_000:.3f}")
        print(f"peak_rss_mb={max(rss) / 1_000_000:.3f}")
        print(f"growth_slope_bytes_per_second={slope:.3f}")


if __name__ == "__main__":
    main()
