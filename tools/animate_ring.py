"""Histogram animation for Experiment 001 logs (per-satellite bins)."""

from __future__ import annotations

import argparse
import math
from bisect import bisect_right
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
from matplotlib import animation

from .common_log import LogEvent, load_events, parse_node_id


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

TIME_SPACE_COLORS = {
    "inject": "#4C78A8",
    "task_created": "#4C78A8",
    "token_issued": "#A0CBE8",
    "forward": "#F58518",
    "task_dispatched": "#F58518",
    "task_forwarded": "#FFBE7D",
    "deliver": "#54A24B",
    "token_validated": "#54A24B",
    "task_accepted": "#72B7B2",
    "complete": "#B79A20",
    "task_completed": "#B79A20",
    "receipt_emitted": "#E45756",
    "deadline_miss": "#E45756",
}

COMPLETION_EVENTS = {"complete", "task_completed"}


def _bin_events(events: List[LogEvent], tbin: float, max_time: float) -> List[List[LogEvent]]:
    bins = int(math.ceil(max_time / tbin)) if max_time > 0 else 1
    grouped: List[List[LogEvent]] = [[] for _ in range(bins)]
    for ev in events:
        idx = min(int(ev.t // tbin), bins - 1)
        grouped[idx].append(ev)
    return grouped


def _writer_for_output(out_path: Path, fps: int):
    if out_path.suffix == ".mp4":
        if animation.writers.is_available("ffmpeg"):
            return animation.FFMpegWriter(fps=fps)
        return None
    return None


def render(
    *,
    events: List[LogEvent],
    out_path: Path,
    n_sats: int,
    n_gs: int,
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

    node_labels = [f"sat{i}" for i in range(n_sats)] + [f"gs{i}" for i in range(n_gs)]
    max_nodes = len(node_labels)
    time_space_events = []
    completion_times = []
    for ev in events:
        payload = ev.payload
        ev_type = payload.get("type") or payload.get("event")
        if ev_type in COMPLETION_EVENTS:
            completion_times.append(ev.t)
        node = payload.get("executor") or payload.get("dst") or payload.get("src")
        if not node or not ev_type:
            continue
        try:
            kind, idx = parse_node_id(node)
        except ValueError:
            continue
        node_index = idx if kind == "sat" else n_sats + idx
        if 0 <= node_index < max_nodes:
            time_space_events.append((ev.t, node_index, ev_type))
    completion_times.sort()

    fig = plt.figure(figsize=(12, 6))
    grid = fig.add_gridspec(2, 2, width_ratios=[2.4, 1.6], height_ratios=[1.3, 1.0])
    ax_hist = fig.add_subplot(grid[:, 0])
    ax_timespace = fig.add_subplot(grid[0, 1])
    ax_completion = fig.add_subplot(grid[1, 1])

    def draw_frame(frame_idx: int):
        nonlocal completed, missed
        ax_hist.clear()
        ax_timespace.clear()
        ax_completion.clear()

        ax_hist.set_xlim(-0.5, n_sats - 0.5)
        ax_hist.set_xlabel("Satellite")
        ax_hist.set_ylabel("Event count (per bin)")
        ax_hist.set_title("Experiment 001 Event Histogram")

        counts: Dict[int, Dict[str, int]] = {i: {e: 0 for e in EVENT_ORDER} for i in range(n_sats)}

        if frame_idx < len(bins):
            for ev in bins[frame_idx]:
                payload = ev.payload
                ev_type = payload.get("type") or payload.get("event")
                if ev_type in COMPLETION_EVENTS:
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
        ax_hist.set_ylim(0, max(1, max_count + 1))

        x_positions = list(range(n_sats))
        bottom = [0] * n_sats

        for ev_type in EVENT_ORDER:
            heights = [counts[i][ev_type] for i in range(n_sats)]
            ax_hist.bar(
                x_positions,
                heights,
                bottom=bottom,
                color=EVENT_COLORS.get(ev_type, "#999999"),
                label=ev_type,
            )
            bottom = [bottom[i] + heights[i] for i in range(n_sats)]

        ax_hist.set_xticks(x_positions)
        ax_hist.set_xticklabels([f"sat{i}" for i in range(n_sats)], rotation=45, ha="right", fontsize=8)
        ax_hist.legend(loc="upper right", fontsize=7, frameon=False, ncol=2)
        ax_hist.text(0.02, 0.95, f"t={int(frame_idx * tbin)}s", transform=ax_hist.transAxes, fontsize=10)
        ax_hist.text(0.02, 0.9, f"completed={completed}", transform=ax_hist.transAxes, fontsize=9)
        ax_hist.text(0.02, 0.85, f"missed={missed}", transform=ax_hist.transAxes, fontsize=9)

        t_now = frame_idx * tbin
        ax_timespace.set_title("Time–Space Diagram", fontsize=10)
        ax_timespace.set_xlabel("Time (s)")
        ax_timespace.set_ylabel("Node")
        ax_timespace.set_xlim(0, max_t)
        ax_timespace.set_ylim(-0.5, max_nodes - 0.5)
        ax_timespace.set_yticks(range(max_nodes))
        ax_timespace.set_yticklabels(node_labels, fontsize=7)

        visible_events = [ev for ev in time_space_events if ev[0] <= t_now]
        for ev_type in {ev[2] for ev in visible_events}:
            points = [(ev[0], ev[1]) for ev in visible_events if ev[2] == ev_type]
            if not points:
                continue
            times, nodes = zip(*points)
            ax_timespace.scatter(
                times,
                nodes,
                s=12,
                color=TIME_SPACE_COLORS.get(ev_type, "#999999"),
                alpha=0.7,
                label=ev_type,
            )
        if visible_events:
            ax_timespace.legend(loc="upper left", fontsize=6, frameon=False, ncol=2)

        ax_completion.set_title("Cumulative Completions", fontsize=10)
        ax_completion.set_xlabel("Time (s)")
        ax_completion.set_ylabel("Completed")
        ax_completion.set_xlim(0, max_t)
        ax_completion.set_ylim(0, max(1, len(completion_times) + 1))
        idx = bisect_right(completion_times, t_now)
        if completion_times:
            ax_completion.step(
                completion_times[:idx],
                list(range(1, idx + 1)),
                where="post",
                color="#2ca02c",
            )
        ax_completion.scatter([t_now], [idx], color="#2ca02c", s=20)

    ani = animation.FuncAnimation(fig, draw_frame, frames=len(bins), interval=1000 / fps)
    writer = _writer_for_output(out_path, fps)
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
        n_gs=args.n_gs,
        fps=args.fps,
        tbin=args.tbin,
        duration=args.duration,
    )
    print(f"Wrote animation to {final_path}")


if __name__ == "__main__":
    main()
