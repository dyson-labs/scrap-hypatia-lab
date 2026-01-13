"""Orbit animation for Experiment 001 logs."""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib import animation

from common_log import LogEvent, load_events


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

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_xlim(-2.0, 2.0)
    ax.set_ylim(-2.0, 2.0)
    ax.axis("off")

    def draw_frame(frame_idx: int):
        nonlocal completed, missed
        ax.clear()
        ax.set_xlim(-2.0, 2.0)
        ax.set_ylim(-2.0, 2.0)
        ax.axis("off")

        # Earth
        earth = plt.Circle((0, 0), 1.0, color="#ddeef7", fill=False, linewidth=1.0)
        ax.add_patch(earth)

        t_now = frame_idx * tbin
        sat_positions = _sat_positions(phases, t_now, radius=1.35, period=5400.0)

        for name, (x, y) in sat_positions.items():
            color = "#1f77b4"
            if name in flash_nodes and frame_idx - flash_nodes[name] <= 2:
                color = "#2ca02c"
            ax.scatter([x], [y], s=30, color=color)
            ax.text(x + 0.03, y + 0.03, name, fontsize=7, color="#333333")

        for name, (x, y) in ground.items():
            ax.scatter([x], [y], s=60, color="#444444")
            ax.text(x + 0.03, y + 0.03, name, fontsize=8, color="#333333")

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
                        ax.plot([xa, xb], [ya, yb], color="#ff7f0e", linewidth=1.5, alpha=0.8)
                        ax.scatter([xb], [yb], s=25, color="#ff7f0e", alpha=0.8)
                if ev_type == "complete":
                    node = payload.get("executor") or dst or src
                    if node:
                        flash_nodes[node] = frame_idx
                        completed += 1
                if ev_type == "deadline_miss":
                    node = payload.get("executor") or dst or src
                    if node and node in positions:
                        ax.scatter([positions[node][0]], [positions[node][1]], s=80, color="#d62728", alpha=0.8)
                        missed += 1

        ax.text(-1.9, 1.8, f"t={int(t_now)}s", fontsize=10)
        ax.text(-1.9, 1.65, f"completed={completed}", fontsize=9)
        ax.text(-1.9, 1.5, f"missed={missed}", fontsize=9)

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
