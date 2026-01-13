"""Experiment 001: ISL-forwarded tasking vs ground-gated baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sim.hypatia_stub import HypatiaStub


SECONDS_PER_STEP = 600  # 10 minutes


@dataclass(frozen=True)
class Task:
    task_id: int
    created_step: int
    deadline_step: int
    target: Tuple[float, float]
    service: str = "imaging"


class TokenProvider:
    def __init__(self, secret: bytes) -> None:
        self.secret = secret

    def issue(self, task: Task, max_hops: int, radius: float) -> bytes:
        payload = {
            "task_id": task.task_id,
            "valid_from": task.created_step,
            "valid_to": task.deadline_step,
            "max_hops": max_hops,
            "radius": radius,
            "target": task.target,
            "allowed_services": [task.service],
        }
        raw = json.dumps(payload, sort_keys=True).encode()
        signature = hashlib.sha256(self.secret + raw).hexdigest()
        payload["sig"] = signature
        return json.dumps(payload, sort_keys=True).encode()

    def validate(self, token_bytes: bytes, task: Task, hop_count: int, now_step: int) -> Tuple[bool, str]:
        try:
            payload = json.loads(token_bytes.decode())
        except Exception:
            return False, "decode_failed"

        sig = payload.pop("sig", None)
        raw = json.dumps(payload, sort_keys=True).encode()
        expected = hashlib.sha256(self.secret + raw).hexdigest()
        if sig != expected:
            return False, "bad_signature"

        if not (payload["valid_from"] <= now_step <= payload["valid_to"]):
            return False, "expired"
        if hop_count > payload["max_hops"]:
            return False, "hop_limit"
        if task.service not in payload.get("allowed_services", []):
            return False, "service_not_allowed"

        target = payload.get("target")
        radius = payload.get("radius")
        if target is None or radius is None:
            return False, "missing_target"

        return True, "ok"

    def receipt(self, task: Task, sat_id: bytes, now_step: int) -> bytes:
        payload = {
            "task_id": task.task_id,
            "sat": sat_id.decode(),
            "completed_step": now_step,
        }
        raw = json.dumps(payload, sort_keys=True).encode()
        signature = hashlib.sha256(self.secret + raw).hexdigest()
        payload["sig"] = signature
        return json.dumps(payload, sort_keys=True).encode()


def _write_event(handle, ts_step: int, event: str, **fields) -> None:
    payload = {"t": ts_step, "event": event}
    payload.update(fields)
    handle.write(json.dumps(payload) + "\n")


def _task_stream(seed: int, total_steps: int, ttl_steps: int) -> List[Task]:
    rng = random.Random(seed)
    tasks: List[Task] = []
    for step in range(total_steps):
        target = (rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0))
        tasks.append(
            Task(
                task_id=step,
                created_step=step,
                deadline_step=step + ttl_steps,
                target=target,
            )
        )
    return tasks


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def run_mode(
    mode: str,
    *,
    seed: int,
    total_steps: int,
    ttl_steps: int,
    n_sats: int,
    n_ground: int,
    max_hops: int,
    radius: float,
    output_path: Path,
) -> None:
    rng = random.Random(seed)
    token_provider = TokenProvider(secret=b"experiment-001")
    hypatia = HypatiaStub(
        rng=rng,
        n_sats=n_sats,
        n_ground=n_ground,
        ttl_steps=ttl_steps,
        crosslink_window=1,
        crosslink_period=6,
        ring_period=4,
        ring_duty=0.5,
    )
    tasks = _task_stream(seed, total_steps, ttl_steps)
    pending: Dict[int, Task] = {}
    dispatched: Dict[int, int] = {}
    in_flight: Dict[int, Dict[bytes, int]] = {}
    accepted: Dict[int, int] = {}
    tokens: Dict[int, bytes] = {}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for step in range(total_steps):
            task = tasks[step]
            _write_event(handle, step, "task_created", task_id=task.task_id)
            pending[task.task_id] = task
            if mode == "isl":
                token = token_provider.issue(task, max_hops=max_hops, radius=radius)
                tokens[task.task_id] = token
                _write_event(handle, step, "token_issued", task_id=task.task_id)

            edges = hypatia.get_active_links()
            edges = [(a.encode(), b.encode()) for a, b in edges]
            ground_contacts = [edge for edge in edges if b"ground" in edge[0] or b"ground" in edge[1]]
            sat_positions = hypatia.get_node_positions()
            ground_available = step % 6 == 0 and bool(ground_contacts)

            # Ground-gated dispatch
            if mode == "ground" and ground_available:
                edge = ground_contacts[0]
                sat = edge[0] if edge[0].startswith(b"sat-") else edge[1]
                pending_ids = sorted(pending.keys())
                if pending_ids:
                    task_id = pending_ids[0]
                    tsk = pending[task_id]
                    dispatched.setdefault(task_id, step)
                    _write_event(handle, step, "task_dispatched", task_id=task_id, sat=sat.decode())
                    _write_event(handle, step, "task_received", task_id=task_id, sat=sat.decode())
                    sat_pos = sat_positions.get(sat.decode())
                    within = sat_pos is not None and _distance(tsk.target, sat_pos) <= radius
                    if within:
                        accepted[task_id] = step
                        _write_event(handle, step, "task_accepted", task_id=task_id, sat=sat.decode())
                        _write_event(handle, step, "task_completed", task_id=task_id, sat=sat.decode())
                        _write_event(
                            handle,
                            step,
                            "receipt_emitted",
                            task_id=task_id,
                            receipt=token_provider.receipt(tsk, sat, step).decode(),
                        )
                        pending.pop(task_id, None)

            # ISL-forwarded dispatch
            if mode == "isl":
                if ground_available:
                    edge = ground_contacts[0]
                    sat = edge[0] if edge[0].startswith(b"sat-") else edge[1]
                    for task_id, tsk in list(pending.items()):
                        if task_id not in dispatched:
                            dispatched[task_id] = step
                            in_flight.setdefault(task_id, {})[sat] = 1
                            _write_event(handle, step, "task_dispatched", task_id=task_id, sat=sat.decode())

                # Propagate over ISLs
                for task_id, holders in list(in_flight.items()):
                    new_holders = dict(holders)
                    for a, b in edges:
                        if b"ground" in a or b"ground" in b:
                            continue
                        if a in holders and holders[a] < max_hops:
                            new_holders.setdefault(b, holders[a] + 1)
                            _write_event(
                                handle,
                                step,
                                "task_forwarded",
                                task_id=task_id,
                                src=a.decode(),
                                dst=b.decode(),
                            )
                        if b in holders and holders[b] < max_hops:
                            new_holders.setdefault(a, holders[b] + 1)
                            _write_event(
                                handle,
                                step,
                                "task_forwarded",
                                task_id=task_id,
                                src=b.decode(),
                                dst=a.decode(),
                            )
                    in_flight[task_id] = new_holders

                # Validate/accept
                for task_id, holders in list(in_flight.items()):
                    tsk = tasks[task_id]
                    token = tokens.get(task_id)
                    if token is None:
                        continue
                    for sat, hop_count in list(holders.items()):
                        sat_pos = sat_positions.get(sat.decode())
                        if sat_pos is None:
                            continue
                        within = _distance(tsk.target, sat_pos) <= radius
                        ok, reason = token_provider.validate(token, tsk, hop_count, step)
                        if not within:
                            ok, reason = False, "outside_area"
                        _write_event(
                            handle,
                            step,
                            "token_validated",
                            task_id=task_id,
                            sat=sat.decode(),
                            ok=ok,
                            reason=reason,
                        )
                        if ok:
                            accepted[task_id] = step
                            _write_event(handle, step, "task_received", task_id=task_id, sat=sat.decode())
                            _write_event(handle, step, "task_accepted", task_id=task_id, sat=sat.decode())
                            _write_event(handle, step, "task_completed", task_id=task_id, sat=sat.decode())
                            _write_event(
                                handle,
                                step,
                                "receipt_emitted",
                                task_id=task_id,
                                receipt=token_provider.receipt(tsk, sat, step).decode(),
                            )
                            pending.pop(task_id, None)
                            in_flight.pop(task_id, None)
                            break
                    if task_id not in pending:
                        continue

            # Deadline accounting
            for t_id, tsk in list(pending.items()):
                if step > tsk.deadline_step:
                    _write_event(handle, step, "deadline_miss", task_id=t_id)
                    pending.pop(t_id, None)

            hypatia.step(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--n-sats", type=int, default=20)
    ap.add_argument("--n-ground", type=int, default=2)
    ap.add_argument("--steps", type=int, default=144)
    ap.add_argument("--ttl-steps", type=int, default=9)
    ap.add_argument("--max-hops", type=int, default=4)
    ap.add_argument("--radius", type=float, default=2.0)
    ap.add_argument("--out-dir", type=str, default="runs")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    run_mode(
        "ground",
        seed=args.seed,
        total_steps=args.steps,
        ttl_steps=args.ttl_steps,
        n_sats=args.n_sats,
        n_ground=args.n_ground,
        max_hops=args.max_hops,
        radius=args.radius,
        output_path=out_dir / "modeA.jsonl",
    )
    run_mode(
        "isl",
        seed=args.seed,
        total_steps=args.steps,
        ttl_steps=args.ttl_steps,
        n_sats=args.n_sats,
        n_ground=args.n_ground,
        max_hops=args.max_hops,
        radius=args.radius,
        output_path=out_dir / "modeB.jsonl",
    )


if __name__ == "__main__":
    main()
