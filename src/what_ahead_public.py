"""Compose runtime-health-verified public visual sources into "what is ahead?".

This module is intentionally pure: health results are injected by the caller.
Network access remains in public_camera_health.py, which makes the decision
chain auditable and easy to test.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional

from .camera_ahead import select_cameras_ahead
from .public_camera_registry import (
    SOURCES,
    PublicVisualSource,
    snapshot_camera_records,
)


def _source_index(
    sources: Iterable[PublicVisualSource],
) -> Dict[str, PublicVisualSource]:
    return {source.source_id: source for source in sources}


def build_public_ahead_report(
    *,
    lat: float,
    lon: float,
    heading: float,
    health: Mapping[str, Mapping[str, Any]],
    sources: Iterable[PublicVisualSource] = SOURCES,
    max_distance_m: float = 5000.0,
    half_cone_deg: float = 55.0,
    limit: int = 3,
) -> Dict[str, Any]:
    """Return only currently health-verified public snapshots ahead."""
    source_list = tuple(sources)
    source_by_id = _source_index(source_list)
    healthy_ids = {
        source_id
        for source_id, status in health.items()
        if isinstance(status, Mapping) and status.get("usable") is True
    }

    records = snapshot_camera_records(
        source_list,
        healthy_ids=healthy_ids,
    )
    candidates = select_cameras_ahead(
        records,
        lat=lat,
        lon=lon,
        heading=heading,
        max_distance_m=max_distance_m,
        half_cone_deg=half_cone_deg,
        limit=limit,
    )

    selected = []
    for item in candidates:
        source = source_by_id[item.camera.camera_id]
        status = dict(health.get(source.source_id) or {})
        selected.append(
            {
                "source_id": source.source_id,
                "name": source.name,
                "provider": source.provider,
                "scene_kind": source.scene_kind,
                "distance_m": round(item.distance_m, 1),
                "bearing_deg": round(item.bearing_deg, 1),
                "angle_delta_deg": round(item.angle_delta_deg, 1),
                "media_kind": source.media_kind,
                "media_url": source.media_url,
                "source_page": source.source_page,
                "health": {
                    "http_status": status.get("http_status"),
                    "content_type": status.get("content_type"),
                    "bytes": status.get("bytes"),
                    "elapsed_ms": status.get("elapsed_ms"),
                },
                "capture_time": None,
                "capture_time_note": (
                    "Provider did not expose a trustworthy capture timestamp; "
                    "do not present retrieval time as image time."
                ),
            }
        )

    vision_requests = [
        {
            "source_id": item["source_id"],
            "image_url": item["media_url"],
            "task": (
                "Describe only observable current scene conditions relevant to "
                "situational awareness: traffic/people/obstructions/weather/"
                "visibility. Do not identify people."
            ),
            "provenance": {
                "provider": item["provider"],
                "source_page": item["source_page"],
                "capture_time": item["capture_time"],
            },
        }
        for item in selected
        if item["media_kind"] == "snapshot"
    ]

    return {
        "ok": True,
        "mode": "public_camera_ahead_lab_v0.1",
        "origin": {
            "lat": lat,
            "lon": lon,
            "heading_deg": heading % 360.0,
        },
        "registered_sources": len(source_list),
        "health_verified_source_ids": sorted(healthy_ids),
        "eligible_snapshot_records": len(records),
        "selected": selected,
        "selected_count": len(selected),
        "vision_requests": vision_requests,
        "answer_state": "ready_for_vision" if vision_requests else "no_verified_public_snapshot_ahead",
        "boundary": (
            "Only intentionally public, runtime-health-verified snapshots are "
            "eligible. No private CCTV, authentication bypass, face search, "
            "or claim of freshness without source evidence."
        ),
    }
