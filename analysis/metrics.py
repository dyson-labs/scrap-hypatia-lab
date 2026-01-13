"""Compute Experiment 001 metrics from JSONL logs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, List


def _read_events(path: Path) -> List[dict]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _latencies(events: Iterable[dict]) -> List[int]:
    created: Dict[int, int] = {}
    completed: Dict[int, int] = {}
    for ev in events:
        if ev["event"] == "task_created":
            created[ev["task_id"]] = ev["t"]
        if ev["event"] == "task_completed":
            completed[ev["task_id"]] = ev["t"]
    latencies = []
    for task_id, t0 in created.items():
        if task_id in completed:
            latencies.append(completed[task_id] - t0)
    return latencies


def _percentile(values: List[int], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = int(round((pct / 100) * (len(values) - 1)))
    return float(values[idx])


def _deadline_miss_rate(events: Iterable[dict]) -> float:
    created = {ev["task_id"] for ev in events if ev["event"] == "task_created"}
    missed = {ev["task_id"] for ev in events if ev["event"] == "deadline_miss"}
    if not created:
        return 0.0
    return len(missed) / len(created)


def _throughput(events: Iterable[dict], duration_steps: int) -> float:
    completed = {ev["task_id"] for ev in events if ev["event"] == "task_completed"}
    if duration_steps <= 0:
        return 0.0
    return len(completed)


def _tasks_blocked_ground(events: Iterable[dict]) -> int:
    created = {}
    dispatched = {}
    for ev in events:
        if ev["event"] == "task_created":
            created[ev["task_id"]] = ev["t"]
        if ev["event"] == "task_dispatched":
            dispatched.setdefault(ev["task_id"], ev["t"])
    blocked = 0
    for task_id, t0 in created.items():
        t1 = dispatched.get(task_id)
        if t1 is not None and t1 > t0:
            blocked += 1
    return blocked


def _isl_message_count(events: Iterable[dict]) -> int:
    return sum(1 for ev in events if ev["event"] == "task_forwarded")


def compute_metrics(events: List[dict], duration_steps: int, mode: str) -> Dict[str, float]:
    latencies = _latencies(events)
    return {
        "mode": mode,
        "p50_latency": _percentile(latencies, 50),
        "p90_latency": _percentile(latencies, 90),
        "p99_latency": _percentile(latencies, 99),
        "deadline_miss_rate": _deadline_miss_rate(events),
        "throughput": _throughput(events, duration_steps),
        "blocked_waiting_ground": _tasks_blocked_ground(events) if mode == "A" else 0,
        "isl_message_count": _isl_message_count(events) if mode == "B" else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode-a", type=str, default="runs/modeA.jsonl")
    ap.add_argument("--mode-b", type=str, default="runs/modeB.jsonl")
    ap.add_argument("--duration-steps", type=int, default=144)
    ap.add_argument("--out-csv", type=str, default="runs/summary.csv")
    args = ap.parse_args()

    events_a = _read_events(Path(args.mode_a))
    events_b = _read_events(Path(args.mode_b))

    metrics_a = compute_metrics(events_a, args.duration_steps, "A")
    metrics_b = compute_metrics(events_b, args.duration_steps, "B")

    print("mode p50 p90 p99 miss_rate throughput blocked_wait_ground isl_msgs")
    print(
        f"A    {metrics_a['p50_latency']:<4} {metrics_a['p90_latency']:<4} {metrics_a['p99_latency']:<4} "
        f"{metrics_a['deadline_miss_rate']:<9.3f} {metrics_a['throughput']:<10.1f} "
        f"{metrics_a['blocked_waiting_ground']:<18} {metrics_a['isl_message_count']}"
    )
    print(
        f"B    {metrics_b['p50_latency']:<4} {metrics_b['p90_latency']:<4} {metrics_b['p99_latency']:<4} "
        f"{metrics_b['deadline_miss_rate']:<9.3f} {metrics_b['throughput']:<10.1f} "
        f"{metrics_b['blocked_waiting_ground']:<18} {metrics_b['isl_message_count']}"
    )

    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics_a.keys()))
        writer.writeheader()
        writer.writerow(metrics_a)
        writer.writerow(metrics_b)


if __name__ == "__main__":
    main()
