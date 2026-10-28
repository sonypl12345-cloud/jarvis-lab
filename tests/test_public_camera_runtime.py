import unittest

from src.public_camera_registry import SOURCES
from src.public_camera_runtime import run_public_camera_ahead


class PublicCameraRuntimeTests(unittest.TestCase):
    def test_runtime_health_then_selection(self):
        def fake_health(sources, timeout):
            self.assertEqual(tuple(sources), SOURCES)
            self.assertEqual(timeout, 3.0)
            return {
                "webcamera:poznan-stary-rynek": {
                    "usable": True,
                    "http_status": 200,
                    "content_type": "image/jpeg",
                    "bytes": 179972,
                    "freshness": {
                        "verified": True,
                        "age_s": 143.0,
                        "reason": "within_max_stale",
                    },
                },
                "lookcam:poznan-hetmanska": {
                    "usable": False,
                    "http_status": 200,
                    "freshness": {
                        "verified": False,
                        "reason": "stale_last_modified",
                    },
                },
                "video-poznan:mtp-602": {
                    "usable": False,
                    "http_status": 503,
                },
            }

        report = run_public_camera_ahead(
            lat=52.4000,
            lon=16.9250,
            heading=37.0,
            health_checker=fake_health,
            timeout=3.0,
            max_distance_m=3000,
        )
        self.assertEqual(report["answer_state"], "ready_for_vision")
        self.assertEqual(
            report["selected"][0]["source_id"],
            "webcamera:poznan-stary-rynek",
        )
        self.assertFalse(report["health"]["lookcam:poznan-hetmanska"]["usable"])


if __name__ == "__main__":
    unittest.main()
