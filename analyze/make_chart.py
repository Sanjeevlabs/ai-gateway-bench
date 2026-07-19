"""Render the AIGatewayBench headline chart from measured results.

Two panels, lower is better:
  - p99 added latency (gateway p99 - direct-to-mock p99, same endpoint)
  - peak RSS (process memory footprint)

Data is read from results/, never hard-coded. Run the bench first, then:
    python analyze/make_chart.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = Path(__file__).resolve().parent.parent / "results"
OUT = Path(__file__).resolve().parent / "overhead_comparison.png"

LITELLM_COLOR = "#00b34a"
OTHER_COLOR = "#3a3f4b"

# gateway key in overhead_summary.json -> (display label, memory summary file)
GATEWAYS = {
    "litellm-rust": ("LiteLLM (Rust)", "mem_litellm_rust_final.txt"),
    "bifrost": ("Bifrost", "mem_bifrost.txt"),
    "portkey": ("Portkey", "mem_portkey_nonstream.txt"),
    "litellm-python": ("LiteLLM (Python v1)", "mem_litellm_python_final.txt"),
}


@dataclass(frozen=True)
class Row:
    label: str
    added_p99_ms: float
    peak_rss_mb: float
    is_litellm: bool


def _peak_rss_mb(summary_file: str) -> float:
    for line in (RESULTS / summary_file).read_text().splitlines():
        if line.startswith("peak_rss_mb="):
            return float(line.split("=", 1)[1])
    raise ValueError(f"peak_rss_mb missing from {summary_file}")


def _load() -> list[Row]:
    overhead = {item["gateway"]: item for item in json.loads((RESULTS / "overhead_summary.json").read_text())}
    rows = []
    for key, (label, mem_file) in GATEWAYS.items():
        rows.append(
            Row(
                label=label,
                added_p99_ms=overhead[key]["latency_p99_overhead_ms"],
                peak_rss_mb=_peak_rss_mb(mem_file),
                is_litellm=(key == "litellm-rust"),
            )
        )
    return rows


def _panel(ax, rows: list[Row], values, unit: str, title: str) -> None:
    order = sorted(range(len(rows)), key=lambda i: values[i], reverse=True)
    labels = [rows[i].label for i in order]
    vals = [values[i] for i in order]
    colors = [LITELLM_COLOR if rows[i].is_litellm else OTHER_COLOR for i in order]
    bars = ax.barh(range(len(rows)), vals, color=colors, height=0.62)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left", pad=10)
    ax.set_xlabel(f"{unit}  (lower is better)", fontsize=9, color="#666")
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(left=False)
    ax.set_xlim(0, max(vals) * 1.18)
    for bar, value in zip(bars, vals):
        ax.text(bar.get_width() + max(vals) * 0.02, bar.get_y() + bar.get_height() / 2,
                f"{value:.1f}", va="center", fontsize=10, fontweight="bold", color="#222")


def main() -> None:
    rows = _load()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 3.6))
    _panel(ax1, rows, [r.added_p99_ms for r in rows], "p99 added latency (ms)",
           "Gateway overhead — p99 added latency")
    _panel(ax2, rows, [r.peak_rss_mb for r in rows], "peak RSS (MB)",
           "Deploy cost — peak memory")
    fig.suptitle("AIGatewayBench: overhead vs a local deterministic mock", fontsize=14,
                 fontweight="bold", x=0.02, ha="left")
    fig.text(0.02, -0.02,
             "First-cut, n=30 per gateway on one host. Overhead = gateway p99 - direct-to-mock p99 on the same "
             "endpoint. LiteLLM Rust on /v1/messages; others on /v1/chat/completions. Portkey measured "
             "non-streaming (streaming errored on v1.15.2). Not a large-sample tail result yet.",
             fontsize=7, color="#888", ha="left")
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
