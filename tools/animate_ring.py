"""Histogram animation for Experiment 001 logs (per-satellite bins)."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
from matplotlib import animation

from tools.common_log import LogEvent, load_events


EVENT_ORDER = [
    "task_created",
    "token_issued",
    "task_dispatched",
    "task_forwarded",
    "token_validated",
    "task_accepted",
    "task_completed",
    "receipt_emitted",
]

EVENT_COLORS = {
    "task_created": "#4C78A8",
    "token_issued": "#A0CBE8",
    "task_dispatched": "#F58518",
    "task_forwarded": "#FFBE7D",
    "token_validated": "#54A24B",
    "task_accepted": "#72B7B2",
    "task_completed": "#B79A20",
    "receipt_emitted": "#E45756",
}


def _bin_events(events: List[LogEvent], tbin: float, max_time: float) -> List[List[LogEvent]]:
    bins = int(math.ceil(max_time / tbin)) if max_time > 0 else 1
    grouped: List[List[LogEvent]] = [[] for _ in range(bins)]
    for ev in events:
        idx = min(int(ev.t // tbin), bins - 1)
        grouped[idx].append(ev)
    return grouped


def _writer_for_output(out_path: Path):
    if out_path.suffix == ".mp4":
        try:
            return animation.FFMpegWriter(fps=24)
        except (RuntimeError, FileNotFoundError):
            return None
    return None


def render(
    *,
    events: List[LogEvent],
    out_path: Path,
    n_sats: int,
    fps: int,
    tbin: float,
    duration: float | None,
) -> Path:
    if not events:
        raise ValueError("No events to animate.")

    start_t = events[0].t
    events = [LogEvent(t=e.t - start_t, payload=e.payload) for e in events]
    max_t = events[-1].t if duration is None else min(duration, events[-1].t)
    bins = _bin_events(events, tbin, max_t)
    completed = 0
    missed = 0

    fig, ax = plt.subplots(figsize=(10, 5))

    def draw_frame(frame_idx: int):
        nonlocal completed, missed
        ax.clear()
        ax.set_xlim(-0.5, n_sats - 0.5)
        ax.set_xlabel("Satellite")
        ax.set_ylabel("Event count (per bin)")
        ax.set_title("Experiment 001 Event Histogram")

        counts: Dict[int, Dict[str, int]] = {i: {e: 0 for e in EVENT_ORDER} for i in range(n_sats)}

        if frame_idx < len(bins):
            for ev in bins[frame_idx]:
                payload = ev.payload
                ev_type = payload.get("type") or payload.get("event")
                if ev_type == "complete":
                    completed += 1
                if ev_type == "deadline_miss":
                    missed += 1
                if ev_type not in EVENT_ORDER:
                    continue
                node = payload.get("executor") or payload.get("dst") or payload.get("src")
                if node and node.lower().startswith("sat"):
                    digits = "".join(ch for ch in node if ch.isdigit())
                    if not digits:
                        continue
                    idx = int(digits)
                    if 0 <= idx < n_sats:
                        counts[idx][ev_type] += 1

        max_count = max((sum(counts[i].values()) for i in range(n_sats)), default=1)
        ax.set_ylim(0, max(1, max_count + 1))

        x_positions = list(range(n_sats))
        bottom = [0] * n_sats

        for ev_type in EVENT_ORDER:
            heights = [counts[i][ev_type] for i in range(n_sats)]
            ax.bar(
                x_positions,
                heights,
                bottom=bottom,
                color=EVENT_COLORS.get(ev_type, "#999999"),
                label=ev_type,
            )
            bottom = [bottom[i] + heights[i] for i in range(n_sats)]

        ax.set_xticks(x_positions)
        ax.set_xticklabels([f"sat{i}" for i in range(n_sats)], rotation=45, ha="right", fontsize=8)
        ax.legend(loc="upper right", fontsize=7, frameon=False, ncol=2)
        ax.text(0.02, 0.95, f"t={int(frame_idx * tbin)}s", transform=ax.transAxes, fontsize=10)
        ax.text(0.02, 0.9, f"completed={completed}", transform=ax.transAxes, fontsize=9)
        ax.text(0.02, 0.85, f"missed={missed}", transform=ax.transAxes, fontsize=9)

    ani = animation.FuncAnimation(fig, draw_frame, frames=len(bins), interval=1000 / fps)
    writer = _writer_for_output(out_path)
    if writer is not None:
        ani.save(out_path, writer=writer)
        return out_path

    gif_path = out_path.with_suffix(".gif")
    ani.save(gif_path, writer=animation.PillowWriter(fps=fps))
    return gif_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n_sats", type=int, default=20)
    ap.add_argument("--n_gs", type=int, default=2)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--tbin", type=float, default=10.0)
    ap.add_argument("--duration", type=float, default=None)
    args = ap.parse_args()

    events = load_events(args.log)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_path = render(
        events=events,
        out_path=out_path,
        n_sats=args.n_sats,
        fps=args.fps,
        tbin=args.tbin,
        duration=args.duration,
    )
    print(f"Wrote animation to {final_path}")


if __name__ == "__main__":
    main()
