import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from public_eyes_registry import (
    eligible_eyes,
    load_webcamera_registry,
    nearest_eyes,
    select_eyes_ahead,
)


class PublicEyesRegistryTests(unittest.TestCase):
    def _registry(self):
        return {
            "schema": "GENESIS_PUBLIC_EYES_REGISTRY_V01",
            "policy": {"raw_images_stored": False},
            "eyes": [
                {
                    "id": "webcamera:ahead",
                    "provider": "webcamera.pl",
                    "name": "Ahead",
                    "lat": 52.010,
                    "lon": 16.000,
                    "page_url": "https://ahead.example/",
                    "preview_url": "https://images.example/ahead.jpg",
                    "premium_hint": False,
                    "outdoor_score": 2,
                },
                {
                    "id": "webcamera:behind",
                    "provider": "webcamera.pl",
                    "name": "Behind",
                    "lat": 51.990,
                    "lon": 16.000,
                    "page_url": "https://behind.example/",
                    "preview_url": "https://images.example/behind.jpg",
                    "premium_hint": False,
                    "outdoor_score": 2,
                },
                {
                    "id": "webcamera:premium",
                    "provider": "webcamera.pl",
                    "name": "Premium",
                    "lat": 52.005,
                    "lon": 16.001,
                    "page_url": "https://premium.example/",
                    "preview_url": "https://images.example/premium.jpg",
                    "premium_hint": True,
                    "outdoor_score": 3,
                },
                {
                    "id": "webcamera:indoor",
                    "provider": "webcamera.pl",
                    "name": "Indoor",
                    "lat": 52.004,
                    "lon": 16.001,
                    "page_url": "https://indoor.example/",
                    "preview_url": "https://images.example/indoor.jpg",
                    "premium_hint": False,
                    "outdoor_score": -2,
                },
            ],
        }

    def _load(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            p.write_text(json.dumps(self._registry()), encoding="utf-8")
            return load_webcamera_registry(p)

    def test_filters_premium_and_indoor_by_default(self):
        eyes = self._load()
        self.assertEqual(
            [x.eye_id for x in eligible_eyes(eyes)],
            ["webcamera:ahead", "webcamera:behind"],
        )

    def test_select_ahead_uses_existing_camera_selector(self):
        eyes = self._load()
        got = select_eyes_ahead(
            eyes, lat=52.0, lon=16.0, heading_deg=0, max_distance_m=5000
        )
        self.assertEqual([x.camera.camera_id for x in got], ["webcamera:ahead"])

    def test_nearest_is_heading_independent_fallback(self):
        eyes = self._load()
        got = nearest_eyes(eyes, lat=52.0, lon=16.0, max_distance_m=5000, limit=2)
        self.assertEqual(len(got), 2)

    def test_registry_rejects_image_persistence(self):
        data = self._registry()
        data["policy"]["raw_images_stored"] = True
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_webcamera_registry(p)


if __name__ == "__main__":
    unittest.main()
