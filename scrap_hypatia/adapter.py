"""Adapter surface between SCRAP experiments and a Hypatia-like simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class HypatiaPacket:
    src: bytes
    dst: bytes
    payload: bytes
    meta: Dict[str, Any] = field(default_factory=dict)


class HypatiaTransport:
    """Bridge SCRAP packets onto a Hypatia-style simulator interface."""

    def __init__(
        self,
        hypatia_sim: Any,
        *,
        attack_p: float = 0.0,
        rng: Optional[Any] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        self.hypatia = hypatia_sim
        self.attack_p = float(attack_p)
        self.rng = rng
        self.metrics = metrics
        self._receivers: Dict[bytes, Callable[[bytes, bytes, bytes, dict], None]] = {}

        self.hypatia.on_delivery(self._on_delivery)
        if hasattr(self.hypatia, "on_drop"):
            self.hypatia.on_drop(self._on_drop)

    def register_receiver(self, dst: bytes, cb: Callable[[bytes, bytes, bytes, dict], None]) -> None:
        self._receivers[dst] = cb

    def recv(self, dst: bytes, cb: Callable[[bytes, bytes, bytes, dict], None]) -> None:
        self.register_receiver(dst, cb)

    def can_send(self, src: bytes, dst: bytes, meta: Optional[dict] = None) -> bool:
        if hasattr(self.hypatia, "can_send"):
            return bool(self.hypatia.can_send(src, dst, meta or {}))
        return True

    def step(self, n: int = 1) -> None:
        if hasattr(self.hypatia, "step"):
            self.hypatia.step(n)


    def send(self, *, src: bytes, dst: bytes, payload: bytes, meta: Optional[dict] = None) -> None:
        if meta is None:
            meta = {}
        meta = dict(meta)

        if "t_inject" not in meta and hasattr(self.hypatia, "now"):
            meta["t_inject"] = int(getattr(self.hypatia, "now"))

        pkt = HypatiaPacket(src=src, dst=dst, payload=payload, meta=meta)
        if self.metrics is not None and hasattr(self.metrics, "on_inject"):
            self.metrics.on_inject(pkt)
        self.hypatia.inject_packet(pkt)

    def _on_delivery(self, pkt: HypatiaPacket) -> None:
        if "t_deliver" not in pkt.meta and hasattr(self.hypatia, "now"):
            pkt.meta["t_deliver"] = int(getattr(self.hypatia, "now"))

        if self.metrics is not None and hasattr(self.metrics, "on_deliver"):
            self.metrics.on_deliver(pkt)

        cb = self._receivers.get(pkt.dst)
        if cb is not None:
            cb(pkt.src, pkt.dst, pkt.payload, pkt.meta)

    def _on_drop(self, pkt: HypatiaPacket, reason: str = "") -> None:
        if self.metrics is not None and hasattr(self.metrics, "on_drop"):
            self.metrics.on_drop(pkt, reason)
