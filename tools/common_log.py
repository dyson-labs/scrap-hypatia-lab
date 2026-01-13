"""Common helpers for parsing experiment JSONL logs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Tuple


@dataclass
class LogEvent:
    t: float
    payload: dict


def _parse_time(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp()
            except ValueError:
                raise ValueError(f"Unsupported time format: {value!r}")
    raise ValueError(f"Unsupported time format: {value!r}")


def load_events(log_path: str | Path) -> List[LogEvent]:
    path = Path(log_path)
    events: List[LogEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        t_raw = payload.get("t")
        if t_raw is None:
            raise ValueError(f"Event missing time field: {payload}")
        t_val = _parse_time(t_raw)
        events.append(LogEvent(t=t_val, payload=payload))
    events.sort(key=lambda e: e.t)
    return events


def parse_node_id(node_id: str) -> Tuple[str, int]:
    raw = node_id.strip()
    lower = raw.lower()
    if lower.startswith("sat"):
        idx = int(lower.replace("sat", "").replace("-", ""))
        return "sat", idx
    if lower.startswith("gs") or lower.startswith("ground"):
        digits = "".join(ch for ch in lower if ch.isdigit())
        idx = int(digits) if digits else 0
        return "gs", idx
    raise ValueError(f"Unrecognized node id: {node_id}")
