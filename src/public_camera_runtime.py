"""Single runtime entry point for public Camera Ahead LAB."""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable, Dict, Iterable, Optional

from .public_camera_health import check_all
from .public_camera_registry import SOURCES, PublicVisualSource
from .what_ahead_public import build_public_ahead_report


HealthChecker = Callable[..., Dict[str, dict]]


def run_public_camera_ahead(
    *,
    lat: float,
    lon: float,
    heading: float,
    sources: Iterable[PublicVisualSource] = SOURCES,
    health_checker: HealthChecker = check_all,
    timeout: float = 8.0,
    max_distance_m: float = 5000.0,
    half_cone_deg: float = 55.0,
    limit: int = 3,
) -> Dict[str, Any]:
    """Health-check public sources, then select verified snapshots ahead."""
    source_list = tuple(sources)
    health = health_checker(source_list, timeout=timeout)
    report = build_public_ahead_report(
        lat=lat,
        lon=lon,
        heading=heading,
        health=health,
        sources=source_list,
        max_distance_m=max_distance_m,
        half_cone_deg=half_cone_deg,
        limit=limit,
    )
    report["health"] = health
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select fresh public visual sources ahead of a position."
    )
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--heading", type=float, required=True)
    parser.add_argument("--max-distance-m", type=float, default=5000.0)
    parser.add_argument("--half-cone-deg", type=float, default=55.0)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    result = run_public_camera_ahead(
        lat=args.lat,
        lon=args.lon,
        heading=args.heading,
        timeout=args.timeout,
        max_distance_m=args.max_distance_m,
        half_cone_deg=args.half_cone_deg,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
