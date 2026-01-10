"""Tiny stand-in for Hypatia so Option 3 plumbing can be landed now.

This is **not** Hypatia.

It intentionally provides a *minimal but useful* orbital-network-ish model so you
can:

1) Embed SCRAP into a time-varying network boundary (Option 3)
2) Measure *headline routing metrics* (reachability, TTFS) in addition to integrity
3) Generate a trace for simple animated visualization

Surface area (what HypatiaTransport needs):

- inject_packet(packet)
- on_delivery(callback) / on_drop(callback)

Additional helpers (optional but useful for experiments/visualization):

- step() / now
- get_node_positions() / get_active_links()

Model sketch:

- N satellites on a ring with slow rotation (good enough to look "orbital")
- Links are time-varying:
    - always-on nearest-neighbor ring links
    - a rotating "window" of additional crosslinks that turns on/off with time
- Packets are store-and-forward at the network boundary:
    - if a path exists at time t, deliver (with optional congestion/outage drop)
    - if no path, keep queued until TTL expires
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, Iterable, List, Optional, Tuple

from scrap_hypatia.adapter import HypatiaPacket


NodeId = bytes
Edge = Tuple[NodeId, NodeId]


@dataclass
class _Queued:
    pkt: HypatiaPacket
    t_inject: int
    ttl_steps: int


class HypatiaStub:
    def __init__(
        self,
        *,
        rng: Optional[random.Random] = None,
        outage_p: float = 0.0,
        congestion_p: float = 0.0,
        n_sats: int = 20,
        dt_s: float = 1.0,
        ttl_steps: int = 30,
        crosslink_window: int = 5,
        crosslink_period: int = 12,
        ring_period: int = 6,
        ring_duty: float = 0.7,
    ):
        self.rng = rng or random.Random()
        self.outage_p = float(outage_p)
        self.congestion_p = float(congestion_p)

        self.n_sats = int(n_sats)
        self.dt_s = float(dt_s)
        self.default_ttl_steps = int(ttl_steps)

        # Extra crosslinks form a "window" that rotates with time
        self.crosslink_window = int(crosslink_window)
        self.crosslink_period = int(crosslink_period)

        # Ring links are intermittent to create meaningful queueing/TTFS.
        self.ring_period = int(ring_period)
        self.ring_duty = float(ring_duty)

        self._t: int = 0
        self._on_delivery: List[Callable[[HypatiaPacket], None]] = []
        self._on_drop: List[Callable[[HypatiaPacket, str], None]] = []
        self._queue: Deque[_Queued] = deque()

        # Pre-create node IDs for stable ordering
        self.nodes: List[NodeId] = [f"sat-{i}".encode() for i in range(self.n_sats)] + [b"ground"]

    # ---------- Event hooks ----------
    def on_delivery(self, cb: Callable[[HypatiaPacket], None]) -> None:
        self._on_delivery.append(cb)

    def on_drop(self, cb: Callable[[HypatiaPacket, str], None]) -> None:
        self._on_drop.append(cb)

    # ---------- Time / state ----------
    @property
    def now(self) -> int:
        """Current discrete timestep."""
        return self._t

    def step(self, n: int = 1) -> None:
        """Advance the network by n steps and attempt delivery of queued packets."""
        for _ in range(int(n)):
            self._t += 1
            self._process_queue()

    # ---------- Visualization helpers ----------
    def get_node_positions(self) -> Dict[str, Tuple[float, float]]:
        """Return normalized (x,y) positions in [-1,1] for animation."""
        positions: Dict[str, Tuple[float, float]] = {}

        # Satellites on ring, slowly rotating
        omega = 2 * math.pi / max(1, self.crosslink_period * 4)
        for i in range(self.n_sats):
            theta = 2 * math.pi * (i / self.n_sats) + omega * self._t
            positions[f"sat-{i}"] = (math.cos(theta), math.sin(theta))

        # Ground at bottom
        positions["ground"] = (0.0, -1.15)
        return positions

    def get_active_links(self) -> List[Tuple[str, str]]:
        """Return active undirected links as pairs of node name strings."""
        edges = self._active_edges()
        out: List[Tuple[str, str]] = []
        for a, b in edges:
            out.append((a.decode(), b.decode()))
        return out

    # ---------- Packet injection ----------
    def inject_packet(self, pkt: HypatiaPacket) -> None:
        """Enqueue a packet; delivery occurs when a path is available."""
        ttl_steps = int(pkt.meta.get("ttl_steps", self.default_ttl_steps))
        self._queue.append(_Queued(pkt=pkt, t_inject=self._t, ttl_steps=ttl_steps))

        # Delivery is processed on the next call to step(), which produces
        # non-zero TTFS and a clearer animation.

    # ---------- Internal network model ----------
    def _active_edges(self) -> List[Edge]:
        """Active edges at current timestep."""
        edges: List[Edge] = []

        # Intermittent ring connectivity among sats (simple contact windows)
        for i in range(self.n_sats):
            # Duty-cycled edge availability
            phase = (self._t + i) % max(1, self.ring_period)
            if phase < int(self.ring_duty * max(1, self.ring_period)):
                a = f"sat-{i}".encode()
                b = f"sat-{(i + 1) % self.n_sats}".encode()
                edges.append((a, b))

        # Ground station has a contact "window" with a subset of sats
        start = (self._t // max(1, self.crosslink_period)) % self.n_sats
        for k in range(self.crosslink_window):
            s = f"sat-{(start + k) % self.n_sats}".encode()
            edges.append((s, b"ground"))

        # Add rotating crosslinks (a simple proxy for changing geometry)
        # Connect sats i -> i+W for a window.
        w = max(2, self.crosslink_window)
        for k in range(self.crosslink_window):
            i = (start + k) % self.n_sats
            a = f"sat-{i}".encode()
            b = f"sat-{(i + w) % self.n_sats}".encode()
            edges.append((a, b))

        return edges

    def _has_path(self, src: NodeId, dst: NodeId, edges: List[Edge]) -> bool:
        """BFS reachability on an undirected graph."""
        if src == dst:
            return True

        nbrs: Dict[NodeId, List[NodeId]] = {}
        for a, b in edges:
            nbrs.setdefault(a, []).append(b)
            nbrs.setdefault(b, []).append(a)

        q = deque([src])
        seen = {src}
        while q:
            u = q.popleft()
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

        edges = self._active_edges()
        keep: Deque[_Queued] = deque()

        while self._queue:
            qd = self._queue.popleft()
            pkt = qd.pkt

            # TTL expiry
            if (self._t - qd.t_inject) > qd.ttl_steps:
                for cb in self._on_drop:
                    cb(pkt, "ttl")
                continue

            # No path right now: keep queued
            if not self._has_path(pkt.src, pkt.dst, edges):
                keep.append(qd)
                continue

            # Path exists: deliver unless dropped by outage/congestion
            if self.rng.random() < self.outage_p:
                for cb in self._on_drop:
                    cb(pkt, "outage")
                continue

            if self.rng.random() < self.congestion_p:
                for cb in self._on_drop:
                    cb(pkt, "congestion")
                continue

            for cb in self._on_delivery:
                cb(pkt)

        self._queue = keep
