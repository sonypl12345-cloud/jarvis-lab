import unittest
from datetime import datetime, timedelta, timezone

from src.dom_bridge_server import build_snapshot, extension_origin, freshness


class DomBridgeTests(unittest.TestCase):
    def test_snapshot_caps_elements_and_has_stable_id(self):
        payload = {"page": {"url": "https://example.com"}, "dom_version": 3, "elements": [{"tag": "button", "name": str(i)} for i in range(510)]}
        first = build_snapshot(payload, "2026-01-01T00:00:00+00:00")
        second = build_snapshot(payload, "2026-01-01T00:01:00+00:00")
        self.assertEqual(first["element_count"], 500)
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])

    def test_dynamic_site_uses_short_ttl(self):
        snapshot = build_snapshot({"page": {"url": "https://x.com/home"}}, "2026-01-01T00:00:00+00:00")
        self.assertEqual(snapshot["freshness"]["ttl_seconds"], 8)

    def test_freshness_expires_and_invalidation_wins(self):
        captured = datetime(2026, 1, 1, tzinfo=timezone.utc)
        snapshot = build_snapshot({"page": {"url": "https://example.com"}}, captured.isoformat())
        self.assertEqual(freshness(snapshot, captured + timedelta(seconds=5))["state"], "fresh")
        self.assertEqual(freshness(snapshot, captured + timedelta(seconds=31))["state"], "stale")
        snapshot["freshness"]["invalidated"] = True
        self.assertEqual(freshness(snapshot, captured + timedelta(seconds=1))["state"], "stale")

    def test_only_extension_origins_are_accepted(self):
        self.assertTrue(extension_origin("chrome-extension://abcdefghijklmnop"))
        self.assertFalse(extension_origin("https://example.com"))
        self.assertFalse(extension_origin(None))


if __name__ == "__main__":
    unittest.main()
