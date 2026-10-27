"""Read-only localhost receiver for explicit browser DOM and public KPD captures."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_snapshot(payload: dict, captured_at: str | None = None) -> dict:
    page = dict(payload.get("page") or {})
    elements = list(payload.get("elements") or [])[:500]
    signature = json.dumps(
        {
            "url": page.get("url"),
            "dom_version": int(payload.get("dom_version", 0)),
            "elements": [
                (item.get("tag"), item.get("role"), item.get("name"), item.get("disabled"))
                for item in elements
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    snapshot_id = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
    ttl = 8 if "x.com" in str(page.get("url", "")) else 30
    return {
        "ok": True,
        "snapshot_id": snapshot_id,
        "captured_at": captured_at or utc_now(),
        "mode": "read_only_explicit_extension_capture",
        "page": page,
        "dom_version": int(payload.get("dom_version", 0)),
        "settled_ms": max(0, int(payload.get("settled_ms", 0))),
        "freshness": {
            "invalidated": False,
            "reason": "explicit_capture",
            "ttl_seconds": ttl,
            "rules": [
                "refresh_before_action",
                "refresh_after_action",
                "refresh_on_mutation",
                "refresh_on_url_change",
                "refresh_on_ttl",
            ],
        },
        "elements": elements,
        "element_count": len(elements),
        "boundary": "DOM evidence only; no click, type, cookie, account, or publishing endpoint.",
    }


def public_kpd_map_url(url: str | None) -> bool:
    try:
        parsed = urlparse(str(url or ""))
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "drogi.gddkia.gov.pl"
        and parsed.path.startswith("/mapy/mapa-informacji-drogowej")
    )


def _text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _safe_kpd_image_path(value) -> str:
    path = _text(value, 700)
    lowered = path.lower()
    if not path:
        return ""
    if lowered.startswith(("javascript:", "data:", "file:")):
        return ""
    if "://" in path:
        parsed = urlparse(path)
        if parsed.scheme != "https" or parsed.hostname != "kpd.gddkia.gov.pl":
            return ""
    return path


def build_camera_snapshot(payload: dict, captured_at: str | None = None) -> dict:
    page = dict(payload.get("page") or {})
    if not public_kpd_map_url(page.get("url")):
        raise ValueError("official_public_kpd_map_required")
    if payload.get("layer_code") != "CamerapointsLayer":
        raise ValueError("unexpected_layer_code")

    clean_points = []
    for point in list(payload.get("points") or [])[:2500]:
        if not isinstance(point, dict):
            continue
        try:
            lat = float(point.get("latitude"))
            lon = float(point.get("longitude"))
        except (TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue

        cameras = []
        for ci, camera in enumerate(list(point.get("cameras") or [])[:8]):
            if not isinstance(camera, dict):
                continue
            images = []
            for image in list(camera.get("images") or [])[:8]:
                if not isinstance(image, dict):
                    continue
                path = _safe_kpd_image_path(image.get("path"))
                if not path:
                    continue
                images.append(
                    {
                        "path": path,
                        "updated_date": _text(image.get("updated_date"), 80),
                    }
                )
            cameras.append(
                {
                    "id": _text(camera.get("id") if camera.get("id") is not None else ci, 80),
                    "images": images,
                }
            )

        clean_points.append(
            {
                "id": _text(point.get("id"), 120),
                "latitude": lat,
                "longitude": lon,
                "name": _text(point.get("name"), 240),
                "road_number": _text(point.get("road_number"), 40),
                "mileage": point.get("mileage"),
                "owner": _text(point.get("owner"), 120),
                "source_name": _text(point.get("source_name"), 120),
                "cameras": cameras,
            }
        )

    signature = json.dumps(
        {
            "source": page.get("url"),
            "points": [
                (
                    p["id"],
                    p["latitude"],
                    p["longitude"],
                    [
                        (
                            c["id"],
                            [(i["path"], i["updated_date"]) for i in c["images"]],
                        )
                        for c in p["cameras"]
                    ],
                )
                for p in clean_points
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    snapshot_id = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]

    return {
        "ok": True,
        "snapshot_id": snapshot_id,
        "captured_at": captured_at or utc_now(),
        "mode": "read_only_public_kpd_camera_layer",
        "page": {
            "title": _text(page.get("title"), 240),
            "url": _text(page.get("url"), 700),
        },
        "layer_code": "CamerapointsLayer",
        "freshness": {
            "invalidated": False,
            "reason": "explicit_public_camera_capture",
            "ttl_seconds": 60,
            "rules": [
                "refresh_before_route_answer",
                "refresh_on_ttl",
                "never_use_private_or_restricted_feeds",
            ],
        },
        "points": clean_points,
        "point_count": len(clean_points),
        "boundary": (
            "Public GDDKiA/KPD camera metadata only; no cookies, credentials, "
            "tokens, browser storage, or unrelated page state."
        ),
    }


def freshness(snapshot: dict, current_time: datetime | None = None) -> dict:
    current_time = current_time or datetime.now(timezone.utc)
    captured = datetime.fromisoformat(snapshot["captured_at"])
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    age = max(0.0, (current_time - captured).total_seconds())
    meta = snapshot.get("freshness", {})
    ttl = int(meta.get("ttl_seconds", 30))
    invalidated = bool(meta.get("invalidated", False))
    stale = invalidated or age > ttl
    return {
        "ok": True,
        "snapshot_id": snapshot.get("snapshot_id"),
        "state": "stale" if stale else "fresh",
        "age_seconds": round(age, 2),
        "ttl_seconds": ttl,
        "invalidated": invalidated,
        "reason": meta.get("reason", "ttl" if stale else "within_ttl"),
        "refresh_required": stale,
    }


def extension_origin(origin: str | None) -> bool:
    return bool(origin and origin.startswith("chrome-extension://") and origin.count("/") == 2)


class BridgeHandler(BaseHTTPRequestHandler):
    latest_path = Path("dom-bridge-latest.json")
    camera_latest_path = Path("kpd-camera-bridge-latest.json")

    def log_message(self, *_args):
        return

    def send_json(self, status: int, payload: dict, origin: str | None = None):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        if extension_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if not extension_origin(origin):
            self.send_json(403, {"ok": False, "error": "extension_origin_required"})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            self.send_json(
                200,
                {
                    "ok": True,
                    "mode": "read_only",
                    "latest_exists": self.latest_path.exists(),
                    "kpd_camera_latest_exists": self.camera_latest_path.exists(),
                },
            )
        elif self.path == "/latest" and self.latest_path.exists():
            self.send_json(200, json.loads(self.latest_path.read_text(encoding="utf-8")))
        elif self.path == "/freshness" and self.latest_path.exists():
            self.send_json(200, freshness(json.loads(self.latest_path.read_text(encoding="utf-8"))))
        elif self.path == "/latest-kpd-cameras" and self.camera_latest_path.exists():
            self.send_json(200, json.loads(self.camera_latest_path.read_text(encoding="utf-8")))
        elif self.path == "/freshness-kpd-cameras" and self.camera_latest_path.exists():
            self.send_json(
                200,
                freshness(json.loads(self.camera_latest_path.read_text(encoding="utf-8"))),
            )
        else:
            self.send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        origin = self.headers.get("Origin")
        if not extension_origin(origin):
            self.send_json(403, {"ok": False, "error": "extension_origin_required"})
            return
        length = min(int(self.headers.get("Content-Length", "0")), 2_000_000)
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"ok": False, "error": "invalid_json"}, origin)
            return

        if self.path == "/capture":
            snapshot = build_snapshot(payload)
            self.latest_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.send_json(
                200,
                {
                    "ok": True,
                    "snapshot_id": snapshot["snapshot_id"],
                    "stored": snapshot["element_count"],
                    "ttl_seconds": snapshot["freshness"]["ttl_seconds"],
                },
                origin,
            )
        elif self.path == "/capture-kpd-cameras":
            try:
                snapshot = build_camera_snapshot(payload)
            except ValueError as exc:
                self.send_json(400, {"ok": False, "error": str(exc)}, origin)
                return
            self.camera_latest_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.send_json(
                200,
                {
                    "ok": True,
                    "snapshot_id": snapshot["snapshot_id"],
                    "stored": snapshot["point_count"],
                    "ttl_seconds": snapshot["freshness"]["ttl_seconds"],
                },
                origin,
            )
        elif self.path == "/invalidate":
            if self.latest_path.exists():
                snapshot = json.loads(self.latest_path.read_text(encoding="utf-8"))
                snapshot["freshness"]["invalidated"] = True
                snapshot["freshness"]["reason"] = str(
                    payload.get("reason", "significant_dom_mutation")
                )[:80]
                snapshot["freshness"]["invalidated_at"] = utc_now()
                self.latest_path.write_text(
                    json.dumps(snapshot, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            self.send_json(200, {"ok": True, "state": "stale"}, origin)
        else:
            self.send_json(404, {"ok": False, "error": "not_found"}, origin)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the read-only Jarvis DOM Bridge receiver."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--output", type=Path, default=Path("dom-bridge-latest.json"))
    parser.add_argument(
        "--camera-output",
        type=Path,
        default=Path("kpd-camera-bridge-latest.json"),
    )
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("The public bridge binds to localhost only.")
    BridgeHandler.latest_path = args.output
    BridgeHandler.camera_latest_path = args.camera_output
    ThreadingHTTPServer((args.host, args.port), BridgeHandler).serve_forever()


if __name__ == "__main__":
    main()
