"""Ring-layout animation for Experiment 001 logs."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib import animation

from tools.common_log import LogEvent, load_events


def _node_positions(n_sats: int, n_gs: int) -> Dict[str, Tuple[float, float]]:
    positions: Dict[str, Tuple[float, float]] = {}
    for i in range(n_sats):
        theta = 2 * math.pi * i / n_sats
        positions[f"sat{i}"] = (math.cos(theta), math.sin(theta))
    if n_gs >= 1:
        positions["GS0"] = (-1.6, 0.0)
    if n_gs >= 2:
        positions["GS1"] = (1.6, 0.0)
    return positions


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
    positions = _node_positions(n_sats, n_gs)
    completed = 0
    missed = 0
    flash_nodes: Dict[str, float] = {}

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_xlim(-2.0, 2.0)
    ax.set_ylim(-2.0, 2.0)
    ax.axis("off")

    base_edges = [(f"sat{i}", f"sat{(i + 1) % n_sats}") for i in range(n_sats)]

    def draw_frame(frame_idx: int):
        nonlocal completed, missed
        ax.clear()
        ax.set_xlim(-2.0, 2.0)
        ax.set_ylim(-2.0, 2.0)
        ax.axis("off")

        for a, b in base_edges:
            xa, ya = positions[a]
            xb, yb = positions[b]
            ax.plot([xa, xb], [ya, yb], color="#cccccc", linewidth=0.5, alpha=0.6)

        # nodes
        for name, (x, y) in positions.items():
            color = "#1f77b4" if name.startswith("sat") else "#444444"
            if name in flash_nodes and frame_idx - flash_nodes[name] <= 2:
                color = "#2ca02c"
            ax.scatter([x], [y], s=60 if name.startswith("GS") else 30, color=color)
            ax.text(x + 0.03, y + 0.03, name, fontsize=8, color="#333333")

        # events in this bin
        if frame_idx < len(bins):
            for ev in bins[frame_idx]:
                payload = ev.payload
                ev_type = payload.get("type") or payload.get("event")
                src = payload.get("src")
                dst = payload.get("dst")
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
                    if node:
                        ax.scatter(
                            [positions.get(node, (0.0, 0.0))[0]],
                            [positions.get(node, (0.0, 0.0))[1]],
                            s=80,
                            color="#d62728",
                            alpha=0.8,
                        )
                        missed += 1

        ax.text(-1.9, 1.8, f"t={int(frame_idx * tbin)}s", fontsize=10)
        ax.text(-1.9, 1.65, f"completed={completed}", fontsize=9)
        ax.text(-1.9, 1.5, f"missed={missed}", fontsize=9)

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
        n_gs=args.n_gs,
        fps=args.fps,
        tbin=args.tbin,
        duration=args.duration,
    )
    print(f"Wrote animation to {final_path}")


if __name__ == "__main__":
    main()
