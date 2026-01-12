"""LEO satellite sampling helpers.

Use TLE sources when available, but keep a synthetic fallback for offline runs.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

EARTH_RADIUS_KM = 6378.137
MU_KM3_S2 = 398600.4418

NAMED_SOURCES = {
    "celestrak:active": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
    "celestrak:leo": "https://celestrak.org/NORAD/elements/gp.php?GROUP=leo&FORMAT=tle",
}


@dataclass(frozen=True)
class SatelliteRecord:
    name: str
    norad_id: str
    constellation: str
    mean_motion_rev_per_day: float
    inclination_deg: float
    altitude_km: float


def _constellation_from_name(name: str) -> str:
    upper = name.upper()
    for prefix in ("STARLINK", "ONEWEB", "IRIDIUM", "GLOBALSTAR", "ORBCOMM", "SWARM", "PLANET", "SPIRE"):
        if upper.startswith(prefix):
            return prefix
    if "STARLINK" in upper:
        return "STARLINK"
    if "ONEWEB" in upper:
        return "ONEWEB"
    if "IRIDIUM" in upper:
        return "IRIDIUM"
    return "OTHER"


def _mean_motion_to_altitude_km(mean_motion_rev_per_day: float) -> float:
    mean_motion_rad_s = mean_motion_rev_per_day * 2 * math.pi / 86400.0
    if mean_motion_rad_s <= 0:
        return 0.0
    semi_major_km = (MU_KM3_S2 / (mean_motion_rad_s**2)) ** (1.0 / 3.0)
    return max(0.0, semi_major_km - EARTH_RADIUS_KM)


def is_placeholder_source(source: str) -> bool:
    lower = source.lower()
    return ("<" in source and ">" in source) or "path-or-url" in lower or "your_tle" in lower


def parse_tle_lines(lines: Iterable[str]) -> List[SatelliteRecord]:
    clean = [line.strip("\n") for line in lines if line.strip()]
    records: List[SatelliteRecord] = []
    for i in range(0, len(clean) - 2, 3):
        name = clean[i].strip()
        line1 = clean[i + 1]
        line2 = clean[i + 2]
        if not (line1.startswith("1") and line2.startswith("2")):
            continue

        norad_id = line1[2:7].strip()
        inclination_deg = float(line2[8:16])
        mean_motion = float(line2[52:63])
        altitude_km = _mean_motion_to_altitude_km(mean_motion)
        constellation = _constellation_from_name(name)
        records.append(
            SatelliteRecord(
                name=name,
                norad_id=norad_id,
                constellation=constellation,
                mean_motion_rev_per_day=mean_motion,
                inclination_deg=inclination_deg,
                altitude_km=altitude_km,
            )
        )
    return records


def _load_with_cache(url: str, cache_dir: Path, ttl_hours: float) -> List[str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    cache_path = cache_dir / f"tle_{digest}.txt"
    now = time.time()

    if cache_path.exists():
        age_hours = (now - cache_path.stat().st_mtime) / 3600.0
        if age_hours <= ttl_hours:
            return cache_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    with urllib.request.urlopen(url, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="ignore")
    cache_path.write_text(text, encoding="utf-8")
    return text.splitlines()


def load_tle_catalog(source: str, *, cache_dir: Optional[Path] = None, cache_ttl_hours: float = 24.0) -> List[SatelliteRecord]:
    if is_placeholder_source(source):
        raise ValueError("TLE source is a placeholder; provide a real path, URL, or named source.")

    source = NAMED_SOURCES.get(source, source)
    cache_dir = cache_dir or Path("data/cache")

    if re.match(r"^https?://", source):
        lines = _load_with_cache(source, cache_dir, cache_ttl_hours)
    else:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"TLE source not found: {source}")
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return parse_tle_lines(lines)


def sample_leo_constellations(
    records: List[SatelliteRecord],
    n_sats: int,
    rng: random.Random,
    overrides: Optional[dict[str, int]] = None,
    max_altitude_km: float = 2000.0,
) -> List[SatelliteRecord]:
    leo = [rec for rec in records if rec.altitude_km <= max_altitude_km]
    if not leo:
        raise ValueError("No LEO satellites found in the provided TLE catalog.")

    by_constellation: dict[str, List[SatelliteRecord]] = {}
    for rec in leo:
        by_constellation.setdefault(rec.constellation, []).append(rec)

    overrides = overrides or {}
    selection: List[SatelliteRecord] = []

    for name, count in overrides.items():
        candidates = by_constellation.get(name, [])
        if not candidates:
            continue
        selection.extend(rng.sample(candidates, min(count, len(candidates))))

    remaining = max(0, n_sats - len(selection))
    if remaining == 0:
        return selection[:n_sats]

    totals = {name: len(group) for name, group in by_constellation.items()}
    total_leo = sum(totals.values())

    if total_leo <= remaining:
        selection.extend(leo)
        return selection[:n_sats]

    shares: List[tuple[str, float]] = []
    for name, count in totals.items():
        shares.append((name, (count / total_leo) * remaining))

    allocations = {name: int(math.floor(share)) for name, share in shares}
    allocated = sum(allocations.values())
    residual = remaining - allocated

    fractional = sorted(shares, key=lambda item: item[1] - math.floor(item[1]), reverse=True)
    for name, _share in fractional:
        if residual <= 0:
            break
        allocations[name] += 1
        residual -= 1

    for name, count in allocations.items():
        if count <= 0:
            continue
        candidates = by_constellation.get(name, [])
        if not candidates:
            continue
        selection.extend(rng.sample(candidates, min(count, len(candidates))))

    if len(selection) < n_sats:
        pool = [rec for rec in leo if rec not in selection]
        if pool:
            selection.extend(rng.sample(pool, min(n_sats - len(selection), len(pool))))

    return selection[:n_sats]


def sample_synthetic_leo(n_sats: int, rng: random.Random) -> List[SatelliteRecord]:
    weights = [0.1, 0.3, 0.2, 0.4]
    names = ["CONSTELLATION-A", "CONSTELLATION-B", "CONSTELLATION-C", "INDEPENDENT"]
    counts = [int(round(n_sats * w)) for w in weights]
    while sum(counts) < n_sats:
        counts[counts.index(max(counts))] += 1
    while sum(counts) > n_sats:
        counts[counts.index(max(counts))] -= 1

    records: List[SatelliteRecord] = []
    for name, count in zip(names, counts):
        for i in range(count):
            mean_motion = rng.uniform(13.0, 16.0)
            inclination = rng.uniform(40.0, 98.0)
            altitude_km = _mean_motion_to_altitude_km(mean_motion)
            records.append(
                SatelliteRecord(
                    name=f"{name}-{i:03d}",
                    norad_id=f"{rng.randrange(10000, 99999)}",
                    constellation=name,
                    mean_motion_rev_per_day=mean_motion,
                    inclination_deg=inclination,
                    altitude_km=altitude_km,
                )
            )
    return records
