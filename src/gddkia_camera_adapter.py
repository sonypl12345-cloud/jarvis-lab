"""Read-only adapter for camera points exposed by the GDDKiA/KPD public map.

The public map JavaScript currently references:
https://kpd.gddkia.gov.pl/amp/api/waypoints/camerapoints.json

A direct anonymous request may return HTTP 401. This adapter deliberately does
not bypass that boundary. Parsing is separated from transport so a caller may
supply data obtained through the official public-map browser session.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .camera_ahead import CameraRecord


KPD_ROOT = "https://kpd.gddkia.gov.pl/"
PUBLIC_MAP_PAGE = "https://drogi.gddkia.gov.pl/mapy/mapa-informacji-drogowej"
CAMERA_POINTS_URL = (
    "https://kpd.gddkia.gov.pl/amp/api/waypoints/camerapoints.json"
)
SOURCE_NAME = "GDDKiA/KPD"


class GDDKiAAccessError(RuntimeError):
    """The official endpoint requires a supported public-map session."""


def _unwrap_points(payload: Any) -> List[Dict[str, Any]]:
    """Accept the response wrappers used by the KPD map transport."""
    value = payload
    for _ in range(3):
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict) and "response" in value:
            value = value["response"]
            continue
        break
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    raise ValueError("unsupported GDDKiA camera payload shape")


def _parse_timestamp(value: Any) -> Optional[float]:
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    try:
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # Do not invent a timezone for KPD wall-clock values.
            return None
        return dt.astimezone(timezone.utc).timestamp()
    except ValueError:
        return None


def _image_url(path: Any) -> Optional[str]:
    if not isinstance(path, str) or not path.strip():
        return None
    return urljoin(KPD_ROOT, path.strip())


def _best_image(cameras: Any) -> tuple[Optional[str], Optional[float], str]:
    """Return newest known image URL, timestamp, and stable camera suffix."""
    if not isinstance(cameras, list):
        return None, None, "0"

    best_url: Optional[str] = None
    best_ts: Optional[float] = None
    best_sort_key = ""
    best_suffix = "0"

    for ci, camera in enumerate(cameras):
        if not isinstance(camera, dict):
            continue
        suffix = str(camera.get("id") or ci)
        images = camera.get("images")
        if not isinstance(images, list):
            continue

        for image in images:
            if not isinstance(image, dict):
                continue
            url = _image_url(image.get("path"))
            if not url:
                continue
            raw_date = image.get("updated_date")
            ts = _parse_timestamp(raw_date)
            sort_key = str(raw_date or "")

            if best_url is None:
                take = True
            elif ts is not None and best_ts is None:
                take = True
            elif ts is not None and best_ts is not None:
                take = ts > best_ts
            elif ts is None and best_ts is None:
                take = sort_key > best_sort_key
            else:
                take = False

            if take:
                best_url = url
                best_ts = ts
                best_sort_key = sort_key
                best_suffix = suffix

    return best_url, best_ts, best_suffix


def parse_camerapoints(
    payload: Any,
    *,
    include_without_image: bool = False,
) -> List[CameraRecord]:
    """Convert a KPD camera-point payload into Camera Ahead records."""
    records: List[CameraRecord] = []

    for point in _unwrap_points(payload):
        try:
            lat = float(point["latitude"])
            lon = float(point["longitude"])
        except (KeyError, TypeError, ValueError):
            continue

        point_id = str(point.get("id") or f"{lat:.6f},{lon:.6f}")
        road = str(point.get("road_number") or "").strip()
        mileage = point.get("mileage")
        point_name = str(point.get("name") or "").strip()

        if point_name:
            name = point_name
        elif road and mileage not in (None, ""):
            name = f"{road} • {mileage} km"
        elif road:
            name = road
        else:
            name = f"KPD camera {point_id}"

        image_url, observed_at, suffix = _best_image(point.get("cameras"))
        if image_url is None and not include_without_image:
            continue

        records.append(
            CameraRecord(
                camera_id=f"gddkia:{point_id}:{suffix}",
                name=name,
                lat=lat,
                lon=lon,
                source=SOURCE_NAME,
                image_url=image_url,
                public=True,
                observed_at=observed_at,
            )
        )

    return records


def fetch_camerapoints_payload(
    *,
    timeout: float = 15.0,
    opener=None,
) -> bytes:
    """Fetch without attempting to defeat access controls.

    The optional opener may represent an already-established legitimate
    official public-map browser session.
    """
    req = Request(
        CAMERA_POINTS_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "Jarvis-Lab-CameraAhead/0.1 (+read-only)",
            "Referer": PUBLIC_MAP_PAGE,
        },
        method="GET",
    )
    open_fn = opener.open if opener is not None else urlopen

    try:
        with open_fn(req, timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise GDDKiAAccessError(
                "GDDKiA camera endpoint requires the supported public-map "
                "session; use browser-session handoff, do not bypass it"
            ) from exc
        raise
