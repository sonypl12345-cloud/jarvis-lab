"""Compose runtime-health-verified public visual sources into "what is ahead?".

This module is intentionally pure: health results are injected by the caller.
Network access remains in public_camera_health.py, which makes the decision
chain auditable and easy to test.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional

from .camera_ahead import distance_m, local_scan_radii, scan_cameras_in_rings
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
    max_distance_m: float = 500.0,
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
    candidates, selected_radius_m, scan_attempts = scan_cameras_in_rings(
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
        "mode": "public_camera_ahead_lab_v0.2_local_rings",
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
        "selected_radius_m": selected_radius_m,
        "scan_attempts": scan_attempts,
        "vision_requests": vision_requests,
        "answer_state": "ready_for_vision" if vision_requests else "no_verified_public_snapshot_ahead",
        "boundary": (
            "Only intentionally public, runtime-health-verified snapshots are "
            "eligible. No private CCTV, authentication bypass, face search, "
            "or claim of freshness without source evidence."
        ),
    }


def build_public_nearby_report(
    *,
    lat: float,
    lon: float,
    health: Mapping[str, Mapping[str, Any]],
    sources: Iterable[PublicVisualSource] = SOURCES,
    max_distance_m: float = 500.0,
    limit: int = 3,
) -> Dict[str, Any]:
    """Find the nearest usable public camera around the owner in local rings.

    This is for "can you see me / what is near me?". It deliberately ignores
    travel heading and does not perform identity recognition.
    """
    source_list = tuple(sources)
    source_by_id = _source_index(source_list)
    healthy_ids = {
        source_id
        for source_id, status in health.items()
        if isinstance(status, Mapping) and status.get("usable") is True
    }
    records = snapshot_camera_records(source_list, healthy_ids=healthy_ids)
    candidates, selected_radius_m, scan_attempts = scan_cameras_in_rings(
        records,
        lat=lat,
        lon=lon,
        heading=None,
        max_distance_m=max_distance_m,
        limit=limit,
    )

    selected = []
    for item in candidates:
        source = source_by_id[item.camera.camera_id]
        status = dict(health.get(source.source_id) or {})
        selected.append({
            "source_id": source.source_id,
            "name": source.name,
            "provider": source.provider,
            "scene_kind": source.scene_kind,
            "distance_m": round(item.distance_m, 1),
            "bearing_deg": round(item.bearing_deg, 1),
            "media_kind": source.media_kind,
            "media_url": source.media_url,
            "source_page": source.source_page,
            "health": {
                "http_status": status.get("http_status"),
                "content_type": status.get("content_type"),
                "bytes": status.get("bytes"),
                "elapsed_ms": status.get("elapsed_ms"),
            },
        })

    vision_requests = [{
        "source_id": item["source_id"],
        "image_url": item["media_url"],
        "task": (
            "Describe observable people/silhouettes, traffic and scene context. "
            "Do not identify any person. The owner may only be described as a "
            "possible candidate when location/time context makes that plausible."
        ),
        "provenance": {
            "provider": item["provider"],
            "source_page": item["source_page"],
            "capture_time": None,
        },
    } for item in selected if item["media_kind"] == "snapshot"]

    ring_diagnostics = []
    for radius in local_scan_radii(max_distance_m):
        registered = [
            source for source in source_list
            if source.public
            and distance_m(lat, lon, source.lat, source.lon) <= radius
        ]
        registered_snapshots = [
            source for source in registered if source.media_kind == "snapshot"
        ]
        healthy_snapshots = [
            source for source in registered_snapshots
            if source.source_id in healthy_ids
        ]
        ring_diagnostics.append({
            "radius_m": radius,
            "registered_public_sources": len(registered),
            "registered_public_snapshots": len(registered_snapshots),
            "healthy_public_snapshots": len(healthy_snapshots),
        })

    registered_within_max = (
        ring_diagnostics[-1]["registered_public_sources"]
        if ring_diagnostics else 0
    )
    healthy_within_max = (
        ring_diagnostics[-1]["healthy_public_snapshots"]
        if ring_diagnostics else 0
    )
    if vision_requests:
        answer_state = "ready_for_vision"
    elif registered_within_max == 0:
        answer_state = "no_registered_public_camera_nearby"
    elif healthy_within_max == 0:
        answer_state = "public_camera_nearby_but_no_usable_snapshot"
    else:
        answer_state = "no_verified_public_snapshot_nearby"

    return {
        "ok": True,
        "mode": "public_camera_nearby_lab_v0.2_local_rings",
        "origin": {"lat": lat, "lon": lon},
        "registered_sources": len(source_list),
        "health_verified_source_ids": sorted(healthy_ids),
        "eligible_snapshot_records": len(records),
        "selected": selected,
        "selected_count": len(selected),
        "selected_radius_m": selected_radius_m,
        "scan_attempts": scan_attempts,
        "ring_diagnostics": ring_diagnostics,
        "vision_requests": vision_requests,
        "answer_state": answer_state,
        "boundary": (
            "Public, runtime-health-verified cameras only; local scan stops at "
            "the configured radius. No private CCTV or identity recognition."
        ),
    }
