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

- LEO satellites sampled from real TLEs when provided (synthetic fallback)
- Satellites move with mean motion; simple 2D projection for visualization
- Links are time-varying:
    - always-on nearest-neighbor ring links
    - a rotating "window" of additional crosslinks that turns on/off with time
    - optional extra intra-constellation links
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
from sim.leo_data import SatelliteRecord, sample_synthetic_leo


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
        n_sats: int = 200,
        n_ground: int = 20,
        satellites: Optional[List[SatelliteRecord]] = None,
        dt_s: float = 1.0,
        ttl_steps: int = 30,
        crosslink_window: int = 5,
        crosslink_period: int = 12,
        ring_period: int = 6,
        ring_duty: float = 0.7,
        constellation_crosslinks: int = 1,
    ):
        self.rng = rng or random.Random()
        self.outage_p = float(outage_p)
        self.congestion_p = float(congestion_p)

        if satellites is None:
            satellites = sample_synthetic_leo(n_sats=n_sats, rng=self.rng)

        self.satellites = satellites
        self.n_sats = len(satellites)
        self.n_ground = int(n_ground)
        self.dt_s = float(dt_s)
        self.default_ttl_steps = int(ttl_steps)

        # Extra crosslinks form a "window" that rotates with time
        self.crosslink_window = int(crosslink_window)
        self.crosslink_period = int(crosslink_period)

        # Ring links are intermittent to create meaningful queueing/TTFS.
        self.ring_period = int(ring_period)
        self.ring_duty = float(ring_duty)
        self.constellation_crosslinks = int(constellation_crosslinks)

        self._t: int = 0
        self._on_delivery: List[Callable[[HypatiaPacket], None]] = []
        self._on_drop: List[Callable[[HypatiaPacket, str], None]] = []
        self._queue: Deque[_Queued] = deque()

        # Pre-create node IDs for stable ordering
        self.sat_nodes: List[NodeId] = [f"sat-{i}".encode() for i in range(self.n_sats)]
        self.ground_nodes: List[NodeId] = [f"ground-{i}".encode() for i in range(self.n_ground)]
        self.nodes: List[NodeId] = self.sat_nodes + self.ground_nodes

        self._constellations: Dict[str, List[int]] = {}
        for idx, sat in enumerate(self.satellites):
            self._constellations.setdefault(sat.constellation, []).append(idx)

        self._min_alt_km = min(sat.altitude_km for sat in self.satellites)
        self._max_alt_km = max(sat.altitude_km for sat in self.satellites)

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

        # Satellites on ring, using real mean motion when available
        for i, sat in enumerate(self.satellites):
            mean_motion = max(0.01, sat.mean_motion_rev_per_day)
            omega = mean_motion * 2 * math.pi / max(1.0, 86400.0 / self.dt_s)
            theta = 2 * math.pi * (i / self.n_sats) + omega * self._t
            inclination = math.radians(sat.inclination_deg)

            alt_span = max(1e-3, self._max_alt_km - self._min_alt_km)
            radius = 1.0 + 0.08 * (sat.altitude_km - self._min_alt_km) / alt_span

            positions[f"sat-{i}"] = (radius * math.cos(theta), radius * math.sin(theta) * math.cos(inclination))

        # Ground stations around a lower ring
        for i in range(self.n_ground):
            theta = 2 * math.pi * (i / max(1, self.n_ground))
            positions[f"ground-{i}"] = (1.05 * math.cos(theta), -1.2 + 0.05 * math.sin(theta))
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

        # Ground stations have contact windows with subsets of sats
        start = (self._t // max(1, self.crosslink_period)) % self.n_sats
        ground_offset = max(1, self.n_sats // max(1, self.n_ground))
        for g_idx, ground in enumerate(self.ground_nodes):
            g_start = (start + g_idx * ground_offset) % self.n_sats
            for k in range(self.crosslink_window):
                s = f"sat-{(g_start + k) % self.n_sats}".encode()
                edges.append((s, ground))

        # Add rotating crosslinks (a simple proxy for changing geometry)
        # Connect sats i -> i+W for a window.
        w = max(2, self.crosslink_window)
        for k in range(self.crosslink_window):
            i = (start + k) % self.n_sats
            a = f"sat-{i}".encode()
            b = f"sat-{(i + w) % self.n_sats}".encode()
            edges.append((a, b))

        # Extra intra-constellation links to mimic operator-owned crosslinks
        if self.constellation_crosslinks > 0:
            for members in self._constellations.values():
                if len(members) < 2:
                    continue
                for extra in range(self.constellation_crosslinks):
                    offset = extra + 1
                    for idx in range(len(members)):
                        a_idx = members[idx]
                        b_idx = members[(idx + offset) % len(members)]
                        phase = (self._t + a_idx + extra) % max(1, self.ring_period)
                        if phase < int(self.ring_duty * max(1, self.ring_period)):
                            a = f"sat-{a_idx}".encode()
                            b = f"sat-{b_idx}".encode()
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
