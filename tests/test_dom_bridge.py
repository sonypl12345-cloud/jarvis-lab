import unittest
from datetime import datetime, timedelta, timezone

from src.dom_bridge_server import (
    build_camera_snapshot,
    build_snapshot,
    extension_origin,
    freshness,
    public_kpd_map_url,
)


class DomBridgeTests(unittest.TestCase):
    def test_snapshot_caps_elements_and_has_stable_id(self):
        payload = {
            "page": {"url": "https://example.com"},
            "dom_version": 3,
            "elements": [{"tag": "button", "name": str(i)} for i in range(510)],
        }
        first = build_snapshot(payload, "2026-01-01T00:00:00+00:00")
        second = build_snapshot(payload, "2026-01-01T00:01:00+00:00")
        self.assertEqual(first["element_count"], 500)
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])

    def test_dynamic_site_uses_short_ttl(self):
        snapshot = build_snapshot(
            {"page": {"url": "https://x.com/home"}},
            "2026-01-01T00:00:00+00:00",
        )
        self.assertEqual(snapshot["freshness"]["ttl_seconds"], 8)

    def test_freshness_expires_and_invalidation_wins(self):
        captured = datetime(2026, 1, 1, tzinfo=timezone.utc)
        snapshot = build_snapshot(
            {"page": {"url": "https://example.com"}},
            captured.isoformat(),
        )
        self.assertEqual(
            freshness(snapshot, captured + timedelta(seconds=5))["state"],
            "fresh",
        )
        self.assertEqual(
            freshness(snapshot, captured + timedelta(seconds=31))["state"],
            "stale",
        )
        snapshot["freshness"]["invalidated"] = True
        self.assertEqual(
            freshness(snapshot, captured + timedelta(seconds=1))["state"],
            "stale",
        )

    def test_only_extension_origins_are_accepted(self):
        self.assertTrue(extension_origin("chrome-extension://abcdefghijklmnop"))
        self.assertFalse(extension_origin("https://example.com"))
        self.assertFalse(extension_origin(None))

    def test_only_official_kpd_map_url_is_accepted(self):
        self.assertTrue(
            public_kpd_map_url(
                "https://drogi.gddkia.gov.pl/mapy/mapa-informacji-drogowej"
            )
        )
        self.assertFalse(
            public_kpd_map_url("https://example.com/mapy/mapa-informacji-drogowej")
        )
        self.assertFalse(
            public_kpd_map_url("http://drogi.gddkia.gov.pl/mapy/mapa-informacji-drogowej")
        )

    def test_public_camera_snapshot_sanitizes_and_caps(self):
        payload = {
            "page": {
                "title": "Mapa informacji drogowej",
                "url": "https://drogi.gddkia.gov.pl/mapy/mapa-informacji-drogowej",
            },
            "layer_code": "CamerapointsLayer",
            "points": [
                {
                    "id": "101",
                    "latitude": 52.4,
                    "longitude": 16.9,
                    "name": "Point",
                    "road_number": "S11",
                    "mileage": 12.3,
                    "cameras": [
                        {
                            "id": "7",
                            "images": [
                                {
                                    "path": "/camera/a.jpg",
                                    "updated_date": "2026-10-27T10:00:00+01:00",
                                },
                                {
                                    "path": "javascript:alert(1)",
                                    "updated_date": "2026-10-27T10:01:00+01:00",
                                },
                            ],
                        }
                    ],
                }
            ],
        }
        snapshot = build_camera_snapshot(
            payload,
            "2026-10-27T09:00:00+00:00",
        )
        self.assertEqual(snapshot["point_count"], 1)
        self.assertEqual(snapshot["freshness"]["ttl_seconds"], 60)
        self.assertEqual(
            snapshot["points"][0]["cameras"][0]["images"],
            [
                {
                    "path": "/camera/a.jpg",
                    "updated_date": "2026-10-27T10:00:00+01:00",
                }
            ],
        )
        self.assertIn("no cookies", snapshot["boundary"])

    def test_camera_snapshot_rejects_wrong_page_or_layer(self):
        with self.assertRaises(ValueError):
            build_camera_snapshot(
                {
                    "page": {"url": "https://example.com/"},
                    "layer_code": "CamerapointsLayer",
                    "points": [],
                }
            )
        with self.assertRaises(ValueError):
            build_camera_snapshot(
                {
                    "page": {
                        "url": "https://drogi.gddkia.gov.pl/mapy/mapa-informacji-drogowej"
                    },
                    "layer_code": "OtherLayer",
                    "points": [],
                }
            )


if __name__ == "__main__":
    unittest.main()
