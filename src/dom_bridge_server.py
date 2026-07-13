"""Read-only localhost receiver for explicit browser DOM captures."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


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
            self.send_json(200, {"ok": True, "mode": "read_only", "latest_exists": self.latest_path.exists()})
        elif self.path == "/latest" and self.latest_path.exists():
            self.send_json(200, json.loads(self.latest_path.read_text(encoding="utf-8")))
        elif self.path == "/freshness" and self.latest_path.exists():
            self.send_json(200, freshness(json.loads(self.latest_path.read_text(encoding="utf-8"))))
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
            self.latest_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            self.send_json(200, {"ok": True, "snapshot_id": snapshot["snapshot_id"], "stored": snapshot["element_count"], "ttl_seconds": snapshot["freshness"]["ttl_seconds"]}, origin)
        elif self.path == "/invalidate":
            if self.latest_path.exists():
                snapshot = json.loads(self.latest_path.read_text(encoding="utf-8"))
                snapshot["freshness"]["invalidated"] = True
                snapshot["freshness"]["reason"] = str(payload.get("reason", "significant_dom_mutation"))[:80]
                snapshot["freshness"]["invalidated_at"] = utc_now()
                self.latest_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            self.send_json(200, {"ok": True, "state": "stale"}, origin)
        else:
            self.send_json(404, {"ok": False, "error": "not_found"}, origin)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the read-only Jarvis DOM Bridge receiver.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--output", type=Path, default=Path("dom-bridge-latest.json"))
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("The public bridge binds to localhost only.")
    BridgeHandler.latest_path = args.output
    ThreadingHTTPServer((args.host, args.port), BridgeHandler).serve_forever()


if __name__ == "__main__":
    main()
