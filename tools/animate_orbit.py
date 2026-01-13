"""Orbit animation for Experiment 001 logs."""

from __future__ import annotations

import argparse
import math
import random
from bisect import bisect_right
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib import animation

from .common_log import LogEvent, load_events, parse_node_id

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


def _ground_positions() -> Dict[str, Tuple[float, float]]:
    gs = {}
    for name, lon_deg in [("GS0", -60.0), ("GS1", 120.0)]:
        theta = math.radians(lon_deg)
        gs[name] = (math.cos(theta), math.sin(theta))
    return gs


def _sat_phase(n_sats: int, seed: int | None) -> List[float]:
    rng = random.Random(seed)
    return [2 * math.pi * i / n_sats + rng.uniform(-0.1, 0.1) for i in range(n_sats)]


def _sat_positions(phases: List[float], t: float, radius: float, period: float) -> Dict[str, Tuple[float, float]]:
    omega = 2 * math.pi / period
    positions: Dict[str, Tuple[float, float]] = {}
    for i, phase in enumerate(phases):
        angle = phase + omega * t
        positions[f"sat{i}"] = (radius * math.cos(angle), radius * math.sin(angle))
    return positions


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
    seed: int | None,
) -> Path:
    if not events:
        raise ValueError("No events to animate.")

    start_t = events[0].t
    events = [LogEvent(t=e.t - start_t, payload=e.payload) for e in events]
    max_t = events[-1].t if duration is None else min(duration, events[-1].t)
    bins = _bin_events(events, tbin, max_t)

    phases = _sat_phase(n_sats, seed)
    ground = _ground_positions()
    completed = 0
    missed = 0
    flash_nodes: Dict[str, float] = {}

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

    fig = plt.figure(figsize=(11, 6))
    grid = fig.add_gridspec(2, 2, width_ratios=[2.2, 1.4], height_ratios=[1.3, 1.0])
    ax_orbit = fig.add_subplot(grid[:, 0])
    ax_timespace = fig.add_subplot(grid[0, 1])
    ax_completion = fig.add_subplot(grid[1, 1])
    ax_orbit.set_xlim(-2.0, 2.0)
    ax_orbit.set_ylim(-2.0, 2.0)
    ax_orbit.axis("off")

    def draw_frame(frame_idx: int):
        nonlocal completed, missed
        ax_orbit.clear()
        ax_timespace.clear()
        ax_completion.clear()
        ax_orbit.set_xlim(-2.0, 2.0)
        ax_orbit.set_ylim(-2.0, 2.0)
        ax_orbit.axis("off")

        # Earth
        earth = plt.Circle((0, 0), 1.0, color="#ddeef7", fill=False, linewidth=1.0)
        ax_orbit.add_patch(earth)

        t_now = frame_idx * tbin
        sat_positions = _sat_positions(phases, t_now, radius=1.35, period=5400.0)

        for name, (x, y) in sat_positions.items():
            color = "#1f77b4"
            if name in flash_nodes and frame_idx - flash_nodes[name] <= 2:
                color = "#2ca02c"
            ax_orbit.scatter([x], [y], s=30, color=color)
            ax_orbit.text(x + 0.03, y + 0.03, name, fontsize=7, color="#333333")

        for name, (x, y) in ground.items():
            ax_orbit.scatter([x], [y], s=60, color="#444444")
            ax_orbit.text(x + 0.03, y + 0.03, name, fontsize=8, color="#333333")

        if frame_idx < len(bins):
            for ev in bins[frame_idx]:
                payload = ev.payload
                ev_type = payload.get("type") or payload.get("event")
                src = payload.get("src")
                dst = payload.get("dst")
                positions = {**sat_positions, **ground}
                if ev_type in {"inject", "forward", "deliver"} and src and dst:
                    if src in positions and dst in positions:
                        xa, ya = positions[src]
                        xb, yb = positions[dst]
                        ax_orbit.plot([xa, xb], [ya, yb], color="#ff7f0e", linewidth=1.5, alpha=0.8)
                        ax_orbit.scatter([xb], [yb], s=25, color="#ff7f0e", alpha=0.8)
                if ev_type in COMPLETION_EVENTS:
                    node = payload.get("executor") or dst or src
                    if node:
                        flash_nodes[node] = frame_idx
                        completed += 1
                if ev_type == "deadline_miss":
                    node = payload.get("executor") or dst or src
                    if node and node in positions:
                        ax_orbit.scatter(
                            [positions[node][0]],
                            [positions[node][1]],
                            s=80,
                            color="#d62728",
                            alpha=0.8,
                        )
                        missed += 1

        ax_orbit.text(-1.9, 1.8, f"t={int(t_now)}s", fontsize=10)
        ax_orbit.text(-1.9, 1.65, f"completed={completed}", fontsize=9)
        ax_orbit.text(-1.9, 1.5, f"missed={missed}", fontsize=9)

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
    ap.add_argument("--seed", type=int, default=None)
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
        seed=args.seed,
    )
    print(f"Wrote animation to {final_path}")


if __name__ == "__main__":
    main()
