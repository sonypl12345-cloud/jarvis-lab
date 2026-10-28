"""Runtime health checks for intentionally public Camera Ahead sources."""

from __future__ import annotations

import hashlib
import time
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .public_camera_registry import PublicVisualSource


def _http_date_epoch(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        return dt.timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def snapshot_freshness(
    *,
    last_modified: Optional[str],
    now_ts: float,
    max_stale_s: Optional[int],
) -> dict:
    """Require provider-backed freshness evidence for current-scene claims."""
    modified_ts = _http_date_epoch(last_modified)
    if modified_ts is None:
        return {
            "verified": False,
            "age_s": None,
            "reason": "last_modified_missing_or_invalid",
        }

    age_s = max(0.0, now_ts - modified_ts)
    if max_stale_s is None:
        return {
            "verified": False,
            "age_s": round(age_s, 1),
            "reason": "no_staleness_contract",
        }

    fresh = age_s <= max_stale_s
    return {
        "verified": fresh,
        "age_s": round(age_s, 1),
        "reason": "within_max_stale" if fresh else "stale_last_modified",
    }


def _fetch(source: PublicVisualSource, timeout: float = 10.0) -> dict:
    req = Request(
        source.media_url,
        headers={
            "User-Agent": "Jarvis-Lab-CameraAhead/0.1 (+read-only)",
            "Accept": "*/*",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        method="GET",
    )
    started = time.time()
    try:
        with urlopen(req, timeout=timeout) as response:
            body = response.read(2_000_000)
            return {
                "ok": 200 <= response.status < 300,
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type", ""),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "last_modified": response.headers.get("Last-Modified"),
                "etag": response.headers.get("ETag"),
                "date": response.headers.get("Date"),
                "elapsed_ms": round((time.time() - started) * 1000),
                "body_prefix": body[:2000],
            }
    except HTTPError as exc:
        return {
            "ok": False,
            "http_status": exc.code,
            "error": f"HTTP {exc.code}",
            "elapsed_ms": round((time.time() - started) * 1000),
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "http_status": None,
            "error": type(exc).__name__,
            "elapsed_ms": round((time.time() - started) * 1000),
        }


def check_source(
    source: PublicVisualSource,
    *,
    timeout: float = 10.0,
    now_ts: Optional[float] = None,
) -> dict:
    result = _fetch(source, timeout=timeout)
    result.update(
        {
            "source_id": source.source_id,
            "name": source.name,
            "provider": source.provider,
            "media_kind": source.media_kind,
            "scene_kind": source.scene_kind,
        }
    )

    if result.get("ok") and source.media_kind == "snapshot":
        ctype = result.get("content_type", "").lower()
        image_ok = ctype.startswith("image/") and result.get("bytes", 0) > 0
        fresh = snapshot_freshness(
            last_modified=result.get("last_modified"),
            now_ts=time.time() if now_ts is None else now_ts,
            max_stale_s=source.max_stale_s,
        )
        result["freshness"] = fresh
        result["usable"] = image_ok and fresh["verified"]
    elif result.get("ok") and source.media_kind == "hls":
        prefix = result.get("body_prefix", b"")
        result["freshness"] = {
            "verified": prefix.lstrip().startswith(b"#EXTM3U"),
            "age_s": None,
            "reason": "live_playlist_reachable",
        }
        result["usable"] = result["freshness"]["verified"]
    else:
        result["freshness"] = {
            "verified": False,
            "age_s": None,
            "reason": "source_unreachable",
        }
        result["usable"] = False

    result.pop("body_prefix", None)
    return result


def check_all(
    sources: Iterable[PublicVisualSource],
    *,
    timeout: float = 10.0,
    now_ts: Optional[float] = None,
) -> Dict[str, dict]:
    return {
        s.source_id: check_source(s, timeout=timeout, now_ts=now_ts)
        for s in sources
    }
