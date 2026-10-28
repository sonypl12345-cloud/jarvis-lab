"""Metadata-only public-eye registry adapter for Camera Ahead.

The registry contains camera metadata only. Image bytes are fetched only after a
small candidate set has been selected, and are never persisted by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from camera_ahead import (
    AheadCandidate,
    CameraRecord,
    angular_distance_deg,
    distance_m,
    select_cameras_ahead,
)


@dataclass(frozen=True)
class PublicEye:
    eye_id: str
    provider: str
    name: str
    lat: float
    lon: float
    page_url: str
    preview_url: str
    premium_hint: bool = False
    outdoor_score: int = 0
    category: str = ""
    media_type: str = "image"
    heading_deg: Optional[float] = None
    heading_conf: Optional[str] = None
    source_priority: int = 2
    feature_url: str = ""


def _payload(path: str | Path, schema: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != schema:
        raise ValueError("unsupported public-eye registry schema")
    if payload.get("policy", {}).get("raw_images_stored") is not False:
        raise ValueError("registry violates no-image-persistence policy")
    return payload


def _coords(row: dict) -> Optional[tuple[float, float]]:
    try:
        lat, lon = float(row["lat"]), float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def load_webcamera_registry(path: str | Path) -> List[PublicEye]:
    payload = _payload(path, "GENESIS_PUBLIC_EYES_REGISTRY_V01")
    eyes: List[PublicEye] = []
    for row in payload.get("eyes", []):
        pos = _coords(row)
        if pos is None:
            continue
        lat, lon = pos
        eyes.append(
            PublicEye(
                eye_id=str(row.get("id") or ""),
                provider=str(row.get("provider") or "webcamera.pl"),
                name=str(row.get("name") or ""),
                lat=lat,
                lon=lon,
                page_url=str(row.get("page_url") or ""),
                preview_url=str(row.get("preview_url") or ""),
                premium_hint=bool(row.get("premium_hint")),
                outdoor_score=int(row.get("outdoor_score") or 0),
                category="webcam",
                media_type="image",
                source_priority=2,
            )
        )
    return eyes


def load_argos_registry(path: str | Path) -> List[PublicEye]:
    payload = _payload(path, "GENESIS_ARGOS_PUBLIC_EYES_WINDOW_V01")
    eyes: List[PublicEye] = []
    for row in payload.get("eyes", []):
        pos = _coords(row)
        if pos is None:
            continue
        lat, lon = pos
        heading = row.get("heading_deg")
        try:
            heading = None if heading is None else float(heading) % 360.0
        except (TypeError, ValueError):
            heading = None
        category = str(row.get("category") or "")
        priority = int(row.get("source_priority") or 0)
        # ARGOS categories describe public outdoor camera families.
        outdoor = 3 if category == "trafico" else 2 if category == "urbanas" else 1
        eyes.append(
            PublicEye(
                eye_id=str(row.get("id") or ""),
                provider=str(row.get("provider") or "argosatlas_public_index"),
                name=str(row.get("name") or ""),
                lat=lat,
                lon=lon,
                page_url="https://argosatlas.com/map/",
                preview_url=str(row.get("preview_url") or ""),
                premium_hint=False,
                outdoor_score=outdoor,
                category=category,
                media_type=str(row.get("media_type") or "image"),
                heading_deg=heading,
                heading_conf=(str(row.get("heading_conf")) if row.get("heading_conf") else None),
                source_priority=priority,
                feature_url=str(row.get("feature_url") or ""),
            )
        )
    return eyes


def load_registries(paths: Sequence[str | Path]) -> List[PublicEye]:
    """Load supported registry files without inventing a new persistence layer."""
    eyes: List[PublicEye] = []
    for path in paths:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        schema = raw.get("schema")
        if schema == "GENESIS_PUBLIC_EYES_REGISTRY_V01":
            eyes.extend(load_webcamera_registry(path))
        elif schema == "GENESIS_ARGOS_PUBLIC_EYES_WINDOW_V01":
            eyes.extend(load_argos_registry(path))
        else:
            raise ValueError(f"unsupported public-eye registry schema: {schema}")
    return eyes


def eligible_eyes(
    eyes: Iterable[PublicEye],
    *,
    allow_premium_hint: bool = False,
    require_outdoor: bool = True,
) -> List[PublicEye]:
    out = []
    for eye in eyes:
        if eye.premium_hint and not allow_premium_hint:
            continue
        if require_outdoor and eye.outdoor_score <= 0:
            continue
        if not eye.preview_url.startswith("https://"):
            continue
        out.append(eye)
    return out


def _orientation_axis_delta(camera_heading: Optional[float], travel_heading: float) -> Optional[float]:
    if camera_heading is None:
        return None
    # A road-facing camera can still be useful when it points against travel:
    # it sees the same road axis from the opposite direction.
    return min(
        angular_distance_deg(camera_heading, travel_heading),
        angular_distance_deg((camera_heading + 180.0) % 360.0, travel_heading),
    )


def select_eyes_ahead(
    eyes: Iterable[PublicEye],
    *,
    lat: float,
    lon: float,
    heading_deg: float,
    max_distance_m: float = 15000.0,
    half_cone_deg: float = 65.0,
    limit: int = 5,
) -> List[AheadCandidate]:
    eligible = eligible_eyes(eyes)
    by_id = {e.eye_id: e for e in eligible}
    records = [
        CameraRecord(
            camera_id=e.eye_id,
            name=e.name,
            lat=e.lat,
            lon=e.lon,
            source=e.provider,
            image_url=e.preview_url,
            public=True,
            observed_at=None,
        )
        for e in eligible
    ]

    # Keep a larger geometric shortlist, then apply source/category/orientation
    # quality. This preserves the existing Camera Ahead geometry as canonical.
    shortlist = select_cameras_ahead(
        records,
        lat=lat,
        lon=lon,
        heading=heading_deg,
        max_distance_m=max_distance_m,
        half_cone_deg=half_cone_deg,
        limit=max(limit * 8, 40),
    )
    reranked: List[AheadCandidate] = []
    for candidate in shortlist:
        eye = by_id[candidate.camera.camera_id]
        priority_penalty = 0.12 * max(0, min(3, eye.source_priority))
        axis_delta = _orientation_axis_delta(eye.heading_deg, heading_deg)
        orientation_penalty = 0.0 if axis_delta is None else 0.20 * min(1.0, axis_delta / 90.0)
        score = candidate.score * (1.0 + priority_penalty + orientation_penalty)
        reranked.append(
            AheadCandidate(
                camera=candidate.camera,
                distance_m=candidate.distance_m,
                bearing_deg=candidate.bearing_deg,
                angle_delta_deg=candidate.angle_delta_deg,
                freshness_s=candidate.freshness_s,
                score=score,
            )
        )

    reranked.sort(key=lambda x: (x.score, x.distance_m, x.angle_delta_deg, x.camera.camera_id))
    return reranked[: max(0, limit)]


def nearest_eyes(
    eyes: Iterable[PublicEye],
    *,
    lat: float,
    lon: float,
    max_distance_m: float = 15000.0,
    limit: int = 5,
) -> List[tuple[PublicEye, float]]:
    ranked = []
    for eye in eligible_eyes(eyes):
        d = distance_m(lat, lon, eye.lat, eye.lon)
        if d <= max_distance_m:
            ranked.append((eye, d))
    ranked.sort(key=lambda x: (x[1], x[0].source_priority, x[0].eye_id))
    return ranked[: max(0, limit)]
