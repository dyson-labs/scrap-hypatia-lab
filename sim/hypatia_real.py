"""Real Hypatia connectivity integration via subprocess-generated schedules."""

from __future__ import annotations

import json
import math
import os
import platform
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from scrap_hypatia.adapter import HypatiaPacket


NodeId = bytes
Edge = Tuple[NodeId, NodeId]


def is_linux_or_wsl() -> bool:
    if platform.system().lower() == "linux":
        return True
    return bool(os.environ.get("WSL_DISTRO_NAME"))


def _parse_cmd(cmd: Optional[str]) -> Optional[List[str]]:
    if not cmd:
        return None
    return shlex.split(cmd)


def _module_available(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def hypatia_cmd_available(cmd: Optional[str]) -> bool:
    parts = _parse_cmd(cmd)
    if not parts:
        return False
    if parts[0] == "python" and "-m" in parts:
        idx = parts.index("-m")
        if idx + 1 < len(parts):
            return _module_available(parts[idx + 1])
        return False
    return shutil.which(parts[0]) is not None


def run_hypatia_command(
    cmd: str,
    output_path: Path,
    *,
    n_sats: int,
    n_ground: int,
    steps: int,
    seed: int,
) -> None:
    parts = _parse_cmd(cmd)
    if not parts:
        raise ValueError("Hypatia command is empty.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    full_cmd = (
        parts
        + [
            "--output",
            str(output_path),
            "--n-sats",
            str(n_sats),
            "--n-ground",
            str(n_ground),
            "--steps",
            str(steps),
            "--seed",
            str(seed),
        ]
    )
    result = subprocess.run(full_cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Hypatia command failed.\n"
            f"Command: {' '.join(full_cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def load_schedule(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "steps" not in payload:
        raise ValueError("Hypatia artifact missing 'steps' field.")
    return payload


def _infer_nodes_from_steps(steps: Iterable[dict]) -> Tuple[List[bytes], List[bytes]]:
    nodes = set()
    for step in steps:
        for a, b in step.get("edges", []):
            nodes.add(a)
            nodes.add(b)
    sat_nodes = sorted([n for n in nodes if str(n).startswith("sat-")])
    ground_nodes = sorted([n for n in nodes if str(n).startswith("ground")])
    return [n.encode() for n in sat_nodes], [n.encode() for n in ground_nodes]


@dataclass
class HypatiaScheduleSim:
    steps: List[Dict[str, Any]]
    sat_nodes: List[bytes]
    ground_nodes: List[bytes]
    ttl_steps: int = 30

    def __post_init__(self) -> None:
        self._t = 0
        self._on_delivery: List[Callable[[HypatiaPacket], None]] = []
        self._on_drop: List[Callable[[HypatiaPacket, str], None]] = []
        self._queue: List[Tuple[int, HypatiaPacket]] = []
        self.n_sats = len(self.sat_nodes)

    @property
    def now(self) -> int:
        return self._t

    def on_delivery(self, cb: Callable[[HypatiaPacket], None]) -> None:
        self._on_delivery.append(cb)

    def on_drop(self, cb: Callable[[HypatiaPacket, str], None]) -> None:
        self._on_drop.append(cb)

    def inject_packet(self, pkt: HypatiaPacket) -> None:
        self._queue.append((self._t, pkt))

    def step(self, n: int = 1) -> None:
        for _ in range(int(n)):
            self._t += 1
            self._process_queue()

    def get_node_positions(self) -> Dict[str, Tuple[float, float]]:
        positions: Dict[str, Tuple[float, float]] = {}
        total = max(1, len(self.sat_nodes))
        for idx, node in enumerate(self.sat_nodes):
            angle = 2 * 3.14159 * (idx / total)
            radius = 0.9 + 0.02 * idx
            positions[node.decode()] = (radius * math.cos(angle), radius * math.sin(angle))
        for idx, node in enumerate(self.ground_nodes):
            positions[node.decode()] = (0.0, -1.2 - 0.05 * idx)
        return positions

    def get_active_links(self) -> List[Tuple[str, str]]:
        edges = self._edges_at_time(self._t)
        return [(a.decode(), b.decode()) for a, b in edges]

    def can_send(self, src: NodeId, dst: NodeId, _meta: Optional[dict] = None) -> bool:
        edges = self._edges_at_time(self._t)
        return self._has_path(src, dst, edges)

    def _edges_at_time(self, t: int) -> List[Edge]:
        idx = min(t, len(self.steps) - 1)
        step = self.steps[idx]
        edges: List[Edge] = []
        for a, b in step.get("edges", []):
            edges.append((a.encode(), b.encode()))
        return edges

    def _has_path(self, src: NodeId, dst: NodeId, edges: List[Edge]) -> bool:
        if src == dst:
            return True
        nbrs: Dict[NodeId, List[NodeId]] = {}
        for a, b in edges:
            nbrs.setdefault(a, []).append(b)
            nbrs.setdefault(b, []).append(a)
        q = [src]
        seen = {src}
        for u in q:
            for v in nbrs.get(u, []):
                if v == dst:
                    return True
                if v not in seen:
                    seen.add(v)
                    q.append(v)
        return False

    def _process_queue(self) -> None:
        if not self._queue:
            return
        edges = self._edges_at_time(self._t)
        keep: List[Tuple[int, HypatiaPacket]] = []
        for t_inject, pkt in self._queue:
            if (self._t - t_inject) > int(pkt.meta.get("ttl_steps", self.ttl_steps)):
                for cb in self._on_drop:
                    cb(pkt, "ttl")
                continue
            if not self._has_path(pkt.src, pkt.dst, edges):
                keep.append((t_inject, pkt))
                continue
            for cb in self._on_delivery:
                cb(pkt)
        self._queue = keep


def build_real_hypatia_sim(
    *,
    hypatia_cmd: Optional[str],
    artifact_path: Optional[str],
    n_sats: int,
    n_ground: int,
    steps: int,
    seed: int,
) -> HypatiaScheduleSim:
    if not hypatia_cmd:
        hypatia_cmd = os.environ.get("HYPATIA_CMD")

    if not hypatia_cmd and not artifact_path:
        raise ValueError("Real Hypatia mode requires --hypatia-cmd or --hypatia-artifact.")

    if hypatia_cmd and not hypatia_cmd_available(hypatia_cmd):
        raise ValueError("Hypatia command is not available. Set --hypatia-cmd or HYPATIA_CMD.")

    artifact = Path(artifact_path) if artifact_path else Path("runs/hypatia_schedule.json")
    if not artifact.exists():
        if not hypatia_cmd:
            raise FileNotFoundError(f"Hypatia artifact not found: {artifact}")
        run_hypatia_command(hypatia_cmd, artifact, n_sats=n_sats, n_ground=n_ground, steps=steps, seed=seed)

    payload = load_schedule(artifact)
    steps_payload = payload.get("steps", [])
    sat_nodes = [n.encode() for n in payload.get("sat_nodes", [])]
    ground_nodes = [n.encode() for n in payload.get("ground_nodes", [])]
    if not sat_nodes or not ground_nodes:
        sat_nodes, ground_nodes = _infer_nodes_from_steps(steps_payload)
    return HypatiaScheduleSim(steps=steps_payload, sat_nodes=sat_nodes, ground_nodes=ground_nodes)
