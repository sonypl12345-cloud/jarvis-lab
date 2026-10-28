"""Runtime health checks for intentionally public Camera Ahead sources."""

from __future__ import annotations

import hashlib
import time
from typing import Dict, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .public_camera_registry import PublicVisualSource


def _fetch(source: PublicVisualSource, timeout: float = 10.0) -> dict:
    req = Request(
        source.media_url,
        headers={
            "User-Agent": "Jarvis-Lab-CameraAhead/0.1 (+read-only)",
            "Accept": "*/*",
            "Cache-Control": "no-cache",
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


def check_source(source: PublicVisualSource, *, timeout: float = 10.0) -> dict:
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
        result["usable"] = ctype.startswith("image/") and result.get("bytes", 0) > 0
    elif result.get("ok") and source.media_kind == "hls":
        prefix = result.get("body_prefix", b"")
        result["usable"] = prefix.lstrip().startswith(b"#EXTM3U")
    else:
        result["usable"] = False

    result.pop("body_prefix", None)
    return result


def check_all(
    sources: Iterable[PublicVisualSource],
    *,
    timeout: float = 10.0,
) -> Dict[str, dict]:
    return {s.source_id: check_source(s, timeout=timeout) for s in sources}
