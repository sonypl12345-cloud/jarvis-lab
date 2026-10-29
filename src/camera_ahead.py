"""Public-camera 'what is ahead?' selector for Jarvis Lab.

This module does not fetch camera images and does not access private CCTV.
It only ranks already-authorized/public camera records by route direction,
distance, and freshness.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, atan2, cos, degrees, radians, sin, sqrt
from typing import Iterable, List, Optional
import time


EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class CameraRecord:
    camera_id: str
    name: str
    lat: float
    lon: float
    source: str
    image_url: Optional[str] = None
    public: bool = True
    observed_at: Optional[float] = None


@dataclass(frozen=True)
class AheadCandidate:
    camera: CameraRecord
    distance_m: float
    bearing_deg: float
    angle_delta_deg: float
    freshness_s: Optional[float]
    score: float


def _normalize_deg(value: float) -> float:
    return value % 360.0


def angular_distance_deg(a: float, b: float) -> float:
    """Smallest absolute angular difference between two headings."""
    diff = (_normalize_deg(a) - _normalize_deg(b) + 180.0) % 360.0 - 180.0
    return abs(diff)


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance using haversine."""
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2.0) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * asin(min(1.0, sqrt(a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2 in degrees [0, 360)."""
    p1, p2 = radians(lat1), radians(lat2)
    dlambda = radians(lon2 - lon1)
    y = sin(dlambda) * cos(p2)
    x = cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dlambda)
    return _normalize_deg(degrees(atan2(y, x)))


def heading_from_points(
    prev_lat: float,
    prev_lon: float,
    lat: float,
    lon: float,
    *,
    min_move_m: float = 4.0,
) -> Optional[float]:
    """Derive travel heading from two GPS samples.

    Returns None when movement is too small to be reliable.
    """
    if distance_m(prev_lat, prev_lon, lat, lon) < min_move_m:
        return None
    return bearing_deg(prev_lat, prev_lon, lat, lon)


def select_cameras_ahead(
    cameras: Iterable[CameraRecord],
    *,
    lat: float,
    lon: float,
    heading: float,
    max_distance_m: float = 500.0,
    half_cone_deg: float = 55.0,
    limit: int = 3,
    now_ts: Optional[float] = None,
    stale_after_s: float = 900.0,
) -> List[AheadCandidate]:
    """Rank public cameras that are geographically ahead of the user.

    The default local-owner scan radius is intentionally 500 m. Wider
    searches must be requested explicitly by the caller.

    Ranking favors:
    1. cameras inside the forward cone,
    2. shorter distance,
    3. smaller angle away from travel direction,
    4. fresher observations when timestamps are available.

    Records marked non-public are always ignored. Stale records are ignored
    only when they include an observation timestamp.
    """
    if max_distance_m <= 0:
        raise ValueError("max_distance_m must be > 0")
    if not (0 < half_cone_deg <= 180):
        raise ValueError("half_cone_deg must be in (0, 180]")
    if limit <= 0:
        return []

    now = time.time() if now_ts is None else now_ts
    heading = _normalize_deg(heading)
    out: List[AheadCandidate] = []

    for camera in cameras:
        if not camera.public:
            continue

        dist = distance_m(lat, lon, camera.lat, camera.lon)
        if dist > max_distance_m:
            continue

        cam_bearing = bearing_deg(lat, lon, camera.lat, camera.lon)
        delta = angular_distance_deg(cam_bearing, heading)
        if delta > half_cone_deg:
            continue

        freshness: Optional[float] = None
        freshness_penalty = 0.0
        if camera.observed_at is not None:
            freshness = max(0.0, now - camera.observed_at)
            if freshness > stale_after_s:
                continue
            freshness_penalty = 0.30 * min(1.0, freshness / stale_after_s)

        angle_penalty = 1.20 * (delta / half_cone_deg)
        score = dist * (1.0 + angle_penalty + freshness_penalty)

        out.append(
            AheadCandidate(
                camera=camera,
                distance_m=dist,
                bearing_deg=cam_bearing,
                angle_delta_deg=delta,
                freshness_s=freshness,
                score=score,
            )
        )

    out.sort(key=lambda x: (x.score, x.distance_m, x.angle_delta_deg, x.camera.camera_id))
    return out[:limit]
