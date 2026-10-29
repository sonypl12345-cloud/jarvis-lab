"""End-to-end LAB runner for the question: "what is ahead?"

Consumes only the sanitized public KPD snapshot written by dom_bridge_server.py.
It does not open browsers, read cookies, access private CCTV, or modify GENESIS.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .camera_ahead import heading_from_points, scan_cameras_in_rings
from .gddkia_camera_adapter import parse_camerapoints


def _iso_from_epoch(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def build_ahead_report(
    snapshot: Dict[str, Any],
    *,
    lat: float,
    lon: float,
    heading: float,
    max_distance_m: float = 500.0,
    limit: int = 3,
    now_ts: Optional[float] = None,
) -> Dict[str, Any]:
    if snapshot.get("mode") != "read_only_public_kpd_camera_layer":
        raise ValueError("public KPD camera snapshot required")
    points = snapshot.get("points")
    if not isinstance(points, list):
        raise ValueError("snapshot points missing")

    cameras = parse_camerapoints(points)
    candidates, selected_radius_m, scan_attempts = scan_cameras_in_rings(
        cameras,
        lat=lat,
        lon=lon,
        heading=heading,
        max_distance_m=max_distance_m,
        limit=limit,
        now_ts=now_ts,
        # KPD image timestamps can be absent or local-wall-clock values.
        # If a parsed timestamp exists, keep the selector conservative.
        stale_after_s=1800.0,
    )

    rows = []
    for item in candidates:
        rows.append(
            {
                "camera_id": item.camera.camera_id,
                "name": item.camera.name,
                "source": item.camera.source,
                "distance_m": round(item.distance_m, 1),
                "bearing_deg": round(item.bearing_deg, 1),
                "angle_delta_deg": round(item.angle_delta_deg, 1),
                "image_url": item.camera.image_url,
                "observed_at": _iso_from_epoch(item.camera.observed_at),
                "freshness_s": (
                    round(item.freshness_s, 1)
                    if item.freshness_s is not None
                    else None
                ),
            }
        )

    return {
        "ok": True,
        "mode": "camera_ahead_lab_v0.2_local_rings",
        "snapshot_id": snapshot.get("snapshot_id"),
        "snapshot_captured_at": snapshot.get("captured_at"),
        "origin": {
            "lat": lat,
            "lon": lon,
            "heading_deg": heading % 360.0,
        },
        "camera_points_seen": len(points),
        "camera_records_with_images": len(cameras),
        "selected": rows,
        "selected_count": len(rows),
        "selected_radius_m": selected_radius_m,
        "scan_attempts": scan_attempts,
        "answer_state": "ready_for_vision" if rows else "no_public_camera_ahead",
        "boundary": (
            "Public GDDKiA/KPD imagery only. Human/vision interpretation "
            "must preserve source and image timestamp."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Select public cameras ahead.")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("kpd-camera-bridge-latest.json"),
    )
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--heading", type=float)
    group.add_argument("--prev", nargs=2, type=float, metavar=("PREV_LAT", "PREV_LON"))
    parser.add_argument("--max-distance-m", type=float, default=500.0)
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    heading = args.heading
    if heading is None:
        prev_lat, prev_lon = args.prev
        heading = heading_from_points(
            prev_lat,
            prev_lon,
            args.lat,
            args.lon,
        )
        if heading is None:
            raise SystemExit("movement too small to derive a reliable heading")

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    report = build_ahead_report(
        snapshot,
        lat=args.lat,
        lon=args.lon,
        heading=heading,
        max_distance_m=args.max_distance_m,
        limit=args.limit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
