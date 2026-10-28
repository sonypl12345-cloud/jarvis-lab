"""Metadata-only public-eye registry adapter for Camera Ahead.

This module never fetches or stores image bytes. It ranks public camera metadata;
actual preview availability/freshness is probed only after a tiny candidate set
has been selected.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, List, Optional

from camera_ahead import CameraRecord, AheadCandidate, distance_m, select_cameras_ahead


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


def load_webcamera_registry(path: str | Path) -> List[PublicEye]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "GENESIS_PUBLIC_EYES_REGISTRY_V01":
        raise ValueError("unsupported public-eye registry schema")
    if payload.get("policy", {}).get("raw_images_stored") is not False:
        raise ValueError("registry violates no-image-persistence policy")

    eyes: List[PublicEye] = []
    for row in payload.get("eyes", []):
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        eyes.append(
            PublicEye(
                eye_id=str(row.get("id") or ""),
                provider=str(row.get("provider") or ""),
                name=str(row.get("name") or ""),
                lat=lat,
                lon=lon,
                page_url=str(row.get("page_url") or ""),
                preview_url=str(row.get("preview_url") or ""),
                premium_hint=bool(row.get("premium_hint")),
                outdoor_score=int(row.get("outdoor_score") or 0),
            )
        )
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
        for e in eligible_eyes(eyes)
    ]
    return select_cameras_ahead(
        records,
        lat=lat,
        lon=lon,
        heading=heading_deg,
        max_distance_m=max_distance_m,
        half_cone_deg=half_cone_deg,
        limit=limit,
    )


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
    ranked.sort(key=lambda x: (x[1], x[0].eye_id))
    return ranked[: max(0, limit)]
