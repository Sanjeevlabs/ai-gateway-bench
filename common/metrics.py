from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * quantile))
    return round(ordered[index], 3)


def summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "p50_ms": percentile(values, 0.50),
        "p99_ms": percentile(values, 0.99),
        "p999_ms": percentile(values, 0.999),
        "max_ms": round(max(values), 3) if values else None,
        "mean_ms": round(statistics.mean(values), 3) if values else None,
    }


def write_result(path: str | Path, result: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
