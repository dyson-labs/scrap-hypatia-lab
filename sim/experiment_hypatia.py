"""Option 3: drive SCRAP via a Hypatia-provided network model.

This experiment is meant to produce *headline metrics* for SCAP/SISL/SCRAP-like
coordination under a time-varying orbital network boundary.

We keep Option 2's adversarial tamper model (attack_p) but we add:

- Reachability / Path feasibility: can a job complete within deadline?
- TTFS (time-to-first-success): time from injection -> verified receipt

Today we use sim.hypatia_stub.HypatiaStub as a minimal time-varying graph.
Replace it with real Hypatia by providing the same surface (inject + callbacks + now/step).
"""

from __future__ import annotations

import argparse
import importlib
import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, Optional

from adapters.scrap_backend import get_backend
from scrap_hypatia.adapter import HypatiaTransport
from sim.hypatia_stub import HypatiaStub
from sim.hypatia_real import build_real_hypatia_sim, is_linux_or_wsl
from sim.leo_data import is_placeholder_source, load_tle_catalog, sample_leo_constellations


def tamper(payload: bytes, rng: random.Random) -> bytes:
    if not payload:
        return payload
    idx = rng.randrange(len(payload))
    flipped = (payload[idx] ^ 0x01).to_bytes(1, "little")
    return payload[:idx] + flipped + payload[idx + 1 :]


@dataclass
class Metrics:
    injected: int = 0
    delivered: int = 0
    dropped: int = 0
    tampered: int = 0
    rejected: int = 0
    verified_ok: int = 0
    verified_bad: int = 0

    # Headline metrics
    ttfs_steps: list[int] = field(default_factory=list)
    completed: int = 0
    deadline_missed: int = 0

    def on_inject(self, _pkt):
        self.injected += 1

    def on_deliver(self, _pkt):
        self.delivered += 1

    def on_drop(self, _pkt, _reason=""):
        self.dropped += 1

    def on_tamper(self, _pkt):
        self.tampered += 1

    def on_reject(self, _req, _reason=""):
        self.rejected += 1


def run_trial(
    *,
    steps: int,
    inject_per_step: int,
    seed: int,
    attack_p: float,
    outage_p: float,
    congestion_p: float,
    ttl_steps: int,
    deadline_steps: int,
    n_sats: int,
    n_ground: int,
    tle_source: Optional[str] = None,
    hypatia_sim: Optional[object] = None,
):
    rng = random.Random(seed)
    metrics = Metrics()

    if hypatia_sim is not None:
        hypatia = hypatia_sim
    else:
        satellites = None
        if tle_source:
            records = load_tle_catalog(tle_source)
            satellites = sample_leo_constellations(records, n_sats=n_sats, rng=rng)

        hypatia = HypatiaStub(
            rng=rng,
            outage_p=outage_p,
            congestion_p=congestion_p,
            ttl_steps=ttl_steps,
            n_sats=n_sats,
            n_ground=n_ground,
            satellites=satellites,
        )
    transport = HypatiaTransport(hypatia, attack_p=attack_p, rng=rng, metrics=metrics)
    scrap = get_backend()

    # Track jobs so we can compute TTFS and deadline feasibility.
    # job_id -> injection timestep
    job_inject_t: Dict[int, int] = {}
    # job_id -> expected receipt bytes
    job_expected: Dict[int, bytes] = {}
    # job_id -> deadline timestep
    job_deadline: Dict[int, int] = {}

    ground_nodes = getattr(hypatia, "ground_nodes", None)
    if ground_nodes is None:
        raise ValueError("Hypatia sim must expose ground_nodes or provide --ground-nodes.")

    def on_rx(_src: bytes, _dst: bytes, payload: bytes, meta: dict):
        """Receipt arrived. Verify and record TTFS."""
        expected = meta.get("expected")
        job_id = meta.get("job_id")
        t_in = meta.get("t_inject")
        t_del = meta.get("t_deliver")

        ok = expected is not None and payload == expected
        if ok:
            metrics.verified_ok += 1
        else:
            metrics.verified_bad += 1

        # TTFS only counts verified-ok completions
        if ok and job_id is not None and t_in is not None and t_del is not None:
            metrics.completed += 1
            metrics.ttfs_steps.append(int(t_del) - int(t_in))

            # Mark job done so we don't double count if duplicate delivery occurs
            job_inject_t.pop(int(job_id), None)
            job_expected.pop(int(job_id), None)
            job_deadline.pop(int(job_id), None)

    for ground in ground_nodes:
        transport.recv(ground, on_rx)

    # --- main simulation loop ---
    job_id = 0
    for _t in range(steps):
        # Inject jobs for this timestep
        for _ in range(inject_per_step):
            sat_nodes = getattr(hypatia, "sat_nodes", None)
            if sat_nodes:
                src = rng.choice(sat_nodes)
            else:
                src = f"sat-{rng.randrange(getattr(hypatia, 'n_sats', n_sats))}".encode()
            dst = rng.choice(ground_nodes)

            token = scrap.issue_capability_token(
                subject=src.decode(),
                caps=["svc:downlink"],
                constraints={"mode": "hypatia"},
            )
            req = scrap.make_bound_task_request(
                token=token,
                payment_hash=b"\x11" * 32,
                task_params={"job": job_id},
            )

            receipt = scrap.make_receipt(req, b"result")
            payload = receipt
            if attack_p > 0 and rng.random() < attack_p:
                payload = tamper(receipt, rng)
                metrics.on_tamper(payload)

            job_inject_t[job_id] = hypatia.now
            job_expected[job_id] = receipt
            job_deadline[job_id] = hypatia.now + deadline_steps

            meta = {
                "expected": receipt,
                "job_id": job_id,
                "ttl_steps": ttl_steps,
            }
            transport.send(src=src, dst=dst, payload=payload, meta=meta)

            job_id += 1

        # Advance sim and try deliver queued packets
        hypatia.step(1)

        # Deadline accounting: jobs still outstanding after deadline are counted as missed
        expired = [jid for jid, dl in job_deadline.items() if hypatia.now > dl]
        for jid in expired:
            metrics.deadline_missed += 1
            job_inject_t.pop(jid, None)
            job_expected.pop(jid, None)
            job_deadline.pop(jid, None)

    availability_rate = (metrics.delivered / metrics.injected) if metrics.injected else 0.0
    verified_rate = (metrics.verified_ok / max(1, (metrics.verified_ok + metrics.verified_bad)))

    # Reachability: fraction of jobs that completed (verified ok) within deadline
    total_jobs = job_id
    reachability = (metrics.completed / total_jobs) if total_jobs else 0.0

    ttfs_mean = mean(metrics.ttfs_steps) if metrics.ttfs_steps else 0.0
    ttfs_p90 = 0.0
    if metrics.ttfs_steps:
        s = sorted(metrics.ttfs_steps)
        idx = int(0.9 * (len(s) - 1))
        ttfs_p90 = float(s[idx])

    return {
        "attack_p": attack_p,
        "outage_p": outage_p,
        "congestion_p": congestion_p,
        "availability": round(availability_rate, 3),
        "verified": round(verified_rate, 3),
        "reachability": round(reachability, 3),
        "ttfs_mean_steps": round(ttfs_mean, 2),
        "ttfs_p90_steps": round(ttfs_p90, 2),
        "injected": metrics.injected,
        "delivered": metrics.delivered,
        "dropped": metrics.dropped,
        "tampered": metrics.tampered,
        "verified_ok": metrics.verified_ok,
        "verified_bad": metrics.verified_bad,
        "completed": metrics.completed,
        "deadline_missed": metrics.deadline_missed,
        "total_jobs": total_jobs,
    }


def main():
    default_tle = Path("data/tle_leo_sample.txt")
    default_source = str(default_tle) if default_tle.exists() else "celestrak:active"

    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument("--inject-per-step", type=int, default=4)
    ap.add_argument("--ttl-steps", type=int, default=30)
    ap.add_argument("--deadline-steps", type=int, default=25)
    ap.add_argument("--n-sats", type=int, default=200)
    ap.add_argument("--n-ground", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument(
        "--hypatia-mode",
        type=str,
        default="stub",
        choices=["stub", "real"],
        help="Select stub or real Hypatia connectivity",
    )
    ap.add_argument(
        "--hypatia-sim",
        type=str,
        default=None,
        help="Import path to a real Hypatia sim class (e.g. pkg.module:ClassName)",
    )
    ap.add_argument(
        "--hypatia-sim-kwargs",
        type=str,
        default="{}",
        help="JSON kwargs for constructing the Hypatia sim",
    )
    ap.add_argument(
        "--ground-nodes",
        type=str,
        default=None,
        help="Comma-separated ground node IDs if the Hypatia sim does not expose ground_nodes",
    )
    ap.add_argument(
        "--hypatia-cmd",
        type=str,
        default=None,
        help="Command to invoke Hypatia (e.g. 'python -m hypatia.cli')",
    )
    ap.add_argument(
        "--hypatia-artifact",
        type=str,
        default=None,
        help="Path to a Hypatia-generated connectivity artifact (JSON).",
    )
    ap.add_argument(
        "--tle-source",
        type=str,
        default=default_source,
        help="TLE file path or URL for real data",
    )
    ap.add_argument("--attack", type=float, default=None, help="Run a single scenario with this attack rate")
    ap.add_argument("--outage", type=float, default=None, help="Run a single scenario with this outage rate")
    ap.add_argument("--congestion", type=float, default=None, help="Run a single scenario with this congestion rate")
    args = ap.parse_args()

    if args.tle_source and is_placeholder_source(args.tle_source):
        args.tle_source = None

    hypatia_sim = None
    if args.hypatia_sim:
        module_name, _, class_name = args.hypatia_sim.partition(":")
        if not module_name or not class_name:
            raise ValueError("--hypatia-sim must be in the form module:ClassName")
        module = importlib.import_module(module_name)
        sim_cls = getattr(module, class_name)
        sim_kwargs = json.loads(args.hypatia_sim_kwargs or "{}")
        hypatia_sim = sim_cls(**sim_kwargs)
        if args.ground_nodes:
            hypatia_sim.ground_nodes = [node.strip().encode() for node in args.ground_nodes.split(",") if node.strip()]
    elif args.hypatia_mode == "real":
        if not is_linux_or_wsl():
            raise ValueError("Real Hypatia mode is supported only on Linux/WSL.")
        hypatia_sim = build_real_hypatia_sim(
            hypatia_cmd=args.hypatia_cmd,
            artifact_path=args.hypatia_artifact,
            n_sats=args.n_sats,
            n_ground=args.n_ground,
            steps=args.steps,
            seed=args.seed,
        )
        if args.ground_nodes:
            hypatia_sim.ground_nodes = [node.strip().encode() for node in args.ground_nodes.split(",") if node.strip()]

    # Default sweep (kept for quick exploration)
    attacks = [0.0, 0.05, 0.2]
    outages = [0.0, 0.1]
    congestions = [0.0, 0.2]

    # If the user specifies attack/outage/congestion, run exactly one scenario.
    if args.attack is not None or args.outage is not None or args.congestion is not None:
        a = float(args.attack or 0.0)
        o = float(args.outage or 0.0)
        c = float(args.congestion or 0.0)

        r = run_trial(
            steps=args.steps,
            inject_per_step=args.inject_per_step,
            seed=args.seed,
            attack_p=a,
            outage_p=o,
            congestion_p=c,
            ttl_steps=args.ttl_steps,
            deadline_steps=args.deadline_steps,
            n_sats=args.n_sats,
            n_ground=args.n_ground,
            tle_source=args.tle_source,
            hypatia_sim=hypatia_sim,
        )

        print(
            "attack outage cong  avail  verified reach  ttfs_mean ttfs_p90 jobs completed missed dropped tampered"
        )
        print(
            "----------------------------------------------------------------------------------------------"
        )
        print(
            f"{a:<6.2f} {o:<6.2f} {c:<5.2f}  "
            f"{r['availability']:<5}  {r['verified']:<7} {r['reachability']:<5} "
            f"{r['ttfs_mean_steps']:<9} {r['ttfs_p90_steps']:<8} "
            f"{r['total_jobs']:<4} {r['completed']:<9} {r['deadline_missed']:<6} "
            f"{r['dropped']:<6} {r['tampered']}"
        )
        return

    print(
        "attack outage cong  avail  verified reach  ttfs_mean ttfs_p90 jobs completed missed dropped tampered"
    )
    print("----------------------------------------------------------------------------------------------")

    for a in attacks:
        for o in outages:
            for c in congestions:
                r = run_trial(
                    steps=args.steps,
                    inject_per_step=args.inject_per_step,
                    seed=args.seed,
                    attack_p=a,
                    outage_p=o,
                    congestion_p=c,
                    ttl_steps=args.ttl_steps,
                    deadline_steps=args.deadline_steps,
                    n_sats=args.n_sats,
                    n_ground=args.n_ground,
                    tle_source=args.tle_source,
                    hypatia_sim=hypatia_sim,
                )
                print(
                    f"{a:<6.2f} {o:<6.2f} {c:<5.2f}  "
                    f"{r['availability']:<5}  {r['verified']:<7} {r['reachability']:<5} "
                    f"{r['ttfs_mean_steps']:<9} {r['ttfs_p90_steps']:<8} "
                    f"{r['total_jobs']:<4} {r['completed']:<9} {r['deadline_missed']:<6} "
                    f"{r['dropped']:<6} {r['tampered']}"
                )


if __name__ == "__main__":
    main()
