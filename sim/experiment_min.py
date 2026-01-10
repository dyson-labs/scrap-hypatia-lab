import random
from dataclasses import dataclass
from adapters.scrap_backend import get_backend

def tamper(b: bytes) -> bytes:
    if not b:
        return b
    i = random.randrange(len(b))
    flipped = (b[i] ^ 0x01).to_bytes(1, "little")
    return b[:i] + flipped + b[i+1:]


@dataclass
class Graph:
    n: int
    edges: set  # set of (u,v) with u < v
    adj: dict   # u -> set(v)

def make_random_graph(n: int, p: float, seed: int = 1) -> Graph:
    random.seed(seed)
    edges = set()
    adj = {i: set() for i in range(n)}
    for u in range(n):
        for v in range(u + 1, n):
            if random.random() < p:
                edges.add((u, v))
                adj[u].add(v)
                adj[v].add(u)
    # ensure connectivity-ish by adding a chain if needed
    for i in range(n - 1):
        if (i, i + 1) not in edges:
            edges.add((i, i + 1))
            adj[i].add(i + 1)
            adj[i + 1].add(i)
    return Graph(n=n, edges=edges, adj=adj)

def bfs_path(g: Graph, src: int, dst: int):
    # shortest path (one of them)
    q = [src]
    prev = {src: None}
    for u in q:
        if u == dst:
            break
        for v in g.adj[u]:
            if v not in prev:
                prev[v] = u
                q.append(v)
    if dst not in prev:
        return None
    path = []
    cur = dst
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path

def path_edges(path):
    es = set()
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        es.add((u, v) if u < v else (v, u))
    return es

def leakage_from_reveals(n_total, e_total, nodes_seen, edges_seen):
    if n_total <= 0 or e_total <= 0:
        return 0.0
    node_frac = len(nodes_seen) / n_total
    edge_frac = len(edges_seen) / e_total
    return round(0.6 * node_frac + 0.4 * edge_frac, 3)

def run_trial(mode: str, disruption: float, load: str, n_jobs: int = 200, seed: int = 7, attack_p: float = 0.0):
    """
    Minimal SCRAP experiment with *computed* topology leakage:
    - We generate a toy time-invariant graph.
    - Each job picks random src/dst and finds a path.
    - Depending on disclosure mode, we "reveal" different topology info.
    - CIA metrics:
        C: leakage score computed from revealed nodes/edges fraction
        I: receipt verify rate (still stubbed = 1.0 for now)
        A: success rate under disruption/load
      Plus: mean control-plane bytes.
    """
    random.seed(seed)
    scrap = get_backend()

    # Toy network
    N = 20
    g = make_random_graph(n=N, p=0.18, seed=seed)
    E = len(g.edges)

    # Disclosure tracking
    nodes_seen = set()
    edges_seen = set()

    # Control-plane byte model (toy)
    base_ctrl = {"revealed": 900, "abstracted": 600, "opaque": 450}[mode]
    load_ctrl = {"low": 1.0, "high": 1.4}[load]

    # Failure model (toy)
    base_fail = {"low": 0.05, "high": 0.20}[load] + disruption

    successes = 0
    verify_ok = 0
    total_ctrl_bytes = 0
    unroutable = 0

    for i in range(n_jobs):
        src = random.randrange(N)
        dst = random.randrange(N)
        while dst == src:
            dst = random.randrange(N)

        path = bfs_path(g, src, dst)
        if not path:
            unroutable += 1
            continue

        # What gets revealed?
        if mode == "revealed":
            nodes_seen.update(path)
            edges_seen.update(path_edges(path))
        elif mode == "abstracted":
            # reveal only abstract stats: path length (no identities)
            # (so we do not add nodes/edges)
            pass
        else:
            # opaque: reveal nothing route-related
            pass

        # pretend SCRAP protocol flow
        token = scrap.issue_capability_token(
            subject=f"sat-{src}",
            caps=["svc:downlink"],
            constraints={"mode": mode},
        )
        req = scrap.make_bound_task_request(
            token=token,
            payment_hash=b"\x11" * 32,
            task_params={"job": i, "load": load, "mode": mode},
        )

        failed = random.random() < base_fail

        ctrl_bytes = int(base_ctrl * load_ctrl)
        if mode == "revealed":
            ctrl_bytes += 250 + 15 * (len(path) - 1)  # route disclosure scales w hops
        elif mode == "abstracted":
            ctrl_bytes += 120 + 4 * (len(path) - 1)   # hop count + summary
        else:
            ctrl_bytes += 40                          # minimal handshake
        total_ctrl_bytes += ctrl_bytes

        if not failed:
            successes += 1

            receipt = scrap.make_receipt(req, b"result")
            if random.random() < attack_p:
                # adversary flips one bit in transit
                receipt = tamper(receipt)

            # strict verify: recompute expected receipt and compare bytes
            expected = scrap.make_receipt(req, b"result")
            if receipt == expected:
                verify_ok += 1

    ran = n_jobs - unroutable
    success_rate = (successes / ran) if ran else 0.0
    integrity_rate = (verify_ok / successes) if successes else 0.0
    mean_ctrl = (total_ctrl_bytes / ran) if ran else 0.0
    leakage = leakage_from_reveals(N, E, nodes_seen, edges_seen)

    return {
        "mode": mode,
        "load": load,
        "disruption": disruption,
        "attack_p": attack_p,
        "success_rate": round(success_rate, 3),
        "integrity_rate": round(integrity_rate, 3),
        "mean_ctrl_bytes": int(mean_ctrl),
        "leakage_score": leakage,
        "nodes_revealed": len(nodes_seen),
        "edges_revealed": len(edges_seen),
        "N": N,
        "E": E,
        "unroutable": unroutable,
    }

def main():
    modes = ["revealed", "abstracted", "opaque"]
    disruptions = [0.0, 0.10]
    attacks = [0.0, 0.05, 0.20]
    loads = ["low", "high"]

    results = []
    for mode in modes:
        for d in disruptions:
            for load in loads:
                for a in attacks:
                    results.append(run_trial(mode, d, load, n_jobs=250, seed=7, attack_p=a))

    print("mode       load  disruption  attack  success  integrity  mean_ctrl  leakage  nodes edges unroutable")
    print("-------------------------------------------------------------------------------------------")
    for r in results:
        print(
            f"{r['mode']:<10} {r['load']:<5} {r['disruption']:<10.2f} {r['attack_p']:<6.2f} "
            f"{r['success_rate']:<7} {r['integrity_rate']:<9} {r['mean_ctrl_bytes']:<9} "
            f"{r['leakage_score']:<7} {r['nodes_revealed']:<5} {r['edges_revealed']:<5} {r['unroutable']}"
        )

if __name__ == "__main__":
    main()







