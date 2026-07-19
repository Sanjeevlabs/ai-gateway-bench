from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = Path(__file__).resolve().parent.parent / "results"
OUT = Path(__file__).resolve().parent
LITELLM_COLOR = "#00b34a"
OTHER_COLOR = "#3a3f4b"
GATEWAYS = {
    "litellm-rust": "LiteLLM (Rust)",
    "litellm-python": "LiteLLM (Python v1)",
    "bifrost": "Bifrost",
    "portkey": "Portkey",
}


def _colors(keys: list[str]) -> list[str]:
    return [LITELLM_COLOR if key == "litellm-rust" else OTHER_COLOR for key in keys]


def _csv(name: str) -> list[dict[str, str]]:
    with (RESULTS / name).open(newline="") as file:
        return list(csv.DictReader(file))


def session_chart() -> None:
    data = {row["gateway"]: row for row in _csv("session_overhead.csv")}
    keys = list(GATEWAYS)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = list(range(len(keys)))
    height = 0.35
    claude = [float(data[key]["claude_code_added_seconds"]) for key in keys]
    codex = [float(data[key]["codex_added_seconds"]) for key in keys]
    ax.barh([v - height / 2 for v in y], claude, height=height, color=_colors(keys), alpha=0.95, label="Claude Code")
    ax.barh([v + height / 2 for v in y], codex, height=height, color=_colors(keys), alpha=0.55, label="Codex-style")
    ax.set_yticks(y, [GATEWAYS[key] for key in keys])
    ax.set_xlabel("Added session wall time (seconds; lower is better)")
    ax.set_title("Whole-session gateway overhead", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(axis="x", alpha=0.2)
    fig.text(0.01, 0.01, "30 deterministic turns; added = gateway total - direct mock total. All four gateways run non-streaming for an apples-to-apples session (Rust and Portkey have no /messages streaming path yet).", fontsize=7, color="#777")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "session_overhead.png", dpi=160, bbox_inches="tight")


def concurrency_chart() -> None:
    data = _csv("latency_vs_concurrency.csv")
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for key, label in GATEWAYS.items():
        rows = [row for row in data if row["gateway"] == key]
        rows.sort(key=lambda row: int(row["concurrency"]))
        ax.plot(
            [int(row["concurrency"]) for row in rows],
            [float(row["p99_added_latency_ms"]) for row in rows],
            marker="o",
            label=label,
            color=LITELLM_COLOR if key == "litellm-rust" else OTHER_COLOR,
        )
    ax.set_xscale("log", base=2)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xlabel("Concurrency")
    ax.set_ylabel("p99 added latency (ms, symlog)")
    ax.set_title("Tail overhead versus concurrency", loc="left", fontweight="bold")
    ax.grid(True, which="both", alpha=0.2)
    ax.legend(frameon=False)
    fig.text(0.01, 0.01, "n=5000 per point; Anthropic /v1/messages body; direct baseline at each concurrency. Concurrency is capped where the direct mock p99 remains within roughly 2x its single-client floor. Signed differences use a symmetric log axis.", fontsize=7, color="#777")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "latency_vs_concurrency.png", dpi=160, bbox_inches="tight")


def cost_chart() -> None:
    data = {row["gateway"]: row for row in _csv("cost_per_million.csv")}
    keys = sorted(GATEWAYS, key=lambda key: float(data[key]["dollars_per_million"]))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    values = [float(data[key]["dollars_per_million"]) for key in keys]
    ax.bar([GATEWAYS[key] for key in keys], values, color=_colors(keys))
    ax.set_ylabel("Estimated dollars per 1M requests")
    ax.set_title("Estimated request cost", loc="left", fontweight="bold")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(axis="y", alpha=0.2)
    for index, value in enumerate(values):
        ax.text(index, value, f"USD {value:.6f}", ha="center", va="bottom", fontsize=8)
    fig.text(0.01, 0.01, r"Estimate only. Estimated \$/1M = ((average CPU fraction × \$/vCPU-hour) + (peak RSS in GB × \$/GB-hour)) ÷ sustained throughput, scaled to 1,000,000 requests. Rates: \$0.04/vCPU-hour and \$0.005/GB-hour; assumes 4 vCPU and 16 GB.", fontsize=7, color="#777")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "cost_per_million.png", dpi=160, bbox_inches="tight")


def ttft_chart() -> None:
    data = {row["gateway"]: row for row in _csv("ttft_overhead.csv")}
    keys = list(GATEWAYS)
    values = [float(data[key]["p50_added_ttft_ms"] or 0) for key in keys]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar([GATEWAYS[key] for key in keys], values, color=_colors(keys))
    ax.set_ylabel("Added TTFT (ms; lower is better)")
    ax.set_title("Streaming time-to-first-token overhead", loc="left", fontweight="bold")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(axis="y", alpha=0.2)
    for index, key in enumerate(keys):
        if data[key]["available"].lower() != "true":
            reason = "no SSE streaming yet\n502 route" if key == "litellm-rust" else "no SSE streaming yet\nOSS 500"
            ax.text(index, 0, reason, ha="center", va="bottom", fontsize=8)
    fig.text(0.01, 0.01, "n=5000, concurrency 16; direct-to-mock /v1/messages baseline. Rust and Portkey streaming unavailable, shown as limitations.", fontsize=7, color="#777")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "ttft_overhead.png", dpi=160, bbox_inches="tight")


if __name__ == "__main__":
    session_chart()
    concurrency_chart()
    cost_chart()
    ttft_chart()
