"""Render a simple SVG visualization for Experiment 001 summary metrics."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def load_summary(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def render_svg(rows: list[dict], output_path: Path) -> None:
    width = 640
    height = 360
    margin = 40
    bar_width = 80
    gap = 60

    modes = [row["mode"] for row in rows]
    p90 = [float(row["p90_latency"]) for row in rows]
    miss = [float(row["deadline_miss_rate"]) for row in rows]

    max_p90 = max(p90) if p90 else 1.0
    max_miss = max(miss) if miss else 1.0

    def bar_height(value: float, max_value: float, scale: float) -> float:
        if max_value <= 0:
            return 0.0
        return (value / max_value) * scale

    chart_height = height - 2 * margin
    p90_scale = chart_height * 0.45
    miss_scale = chart_height * 0.45

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{margin}" y="{margin - 10}" font-size="14" font-family="Arial">Experiment 001 Summary</text>',
    ]

    for idx, mode in enumerate(modes):
        x0 = margin + idx * (bar_width * 2 + gap)
        p90_h = bar_height(p90[idx], max_p90, p90_scale)
        miss_h = bar_height(miss[idx], max_miss, miss_scale)

        p90_y = margin + p90_scale - p90_h
        miss_y = margin + p90_scale + 20 + miss_scale - miss_h

        svg_lines.append(f'<rect x="{x0}" y="{p90_y}" width="{bar_width}" height="{p90_h}" fill="#4C78A8"/>')
        svg_lines.append(
            f'<rect x="{x0 + bar_width + 10}" y="{miss_y}" width="{bar_width}" height="{miss_h}" fill="#F58518"/>'
        )
        svg_lines.append(
            f'<text x="{x0}" y="{height - margin + 15}" font-size="12" font-family="Arial">Mode {mode}</text>'
        )

    legend_y = margin + p90_scale + 10
    svg_lines.append(f'<rect x="{width - 180}" y="{legend_y}" width="12" height="12" fill="#4C78A8"/>')
    svg_lines.append(
        f'<text x="{width - 160}" y="{legend_y + 10}" font-size="12" font-family="Arial">p90 latency</text>'
    )
    svg_lines.append(
        f'<rect x="{width - 180}" y="{legend_y + 20}" width="12" height="12" fill="#F58518"/>'
    )
    svg_lines.append(
        f'<text x="{width - 160}" y="{legend_y + 30}" font-size="12" font-family="Arial">deadline miss rate</text>'
    )

    svg_lines.append("</svg>")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(svg_lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", type=str, default="runs/summary.csv")
    ap.add_argument("--out", type=str, default="runs/summary.svg")
    args = ap.parse_args()

    rows = load_summary(Path(args.summary))
    render_svg(rows, Path(args.out))


if __name__ == "__main__":
    main()
