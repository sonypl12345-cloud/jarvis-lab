import unittest

from src.public_camera_registry import SOURCES
from src.what_ahead_public import build_public_ahead_report, build_public_nearby_report


class PublicWhatAheadTests(unittest.TestCase):
    def test_selects_verified_source_ahead(self):
        health = {
            "webcamera:poznan-stary-rynek": {
                "usable": True,
                "http_status": 200,
                "content_type": "image/jpeg",
                "bytes": 100000,
                "elapsed_ms": 100,
            },
            "lookcam:poznan-hetmanska": {
                "usable": False,
                "http_status": 200,
                "content_type": "image/jpeg",
            },
            "video-poznan:mtp-602": {
                "usable": False,
                "http_status": 503,
            },
        }
        report = build_public_ahead_report(
            lat=52.4000,
            lon=16.9250,
            heading=37.0,
            health=health,
            max_distance_m=3000,
        )
        self.assertEqual(report["answer_state"], "ready_for_vision")
        self.assertEqual(report["selected_count"], 1)
        self.assertEqual(
            report["selected"][0]["source_id"],
            "webcamera:poznan-stary-rynek",
        )
        self.assertEqual(len(report["vision_requests"]), 1)
        self.assertIsNone(report["selected"][0]["capture_time"])

    def test_dead_or_stale_source_cannot_be_promoted(self):
        health = {
            source.source_id: {"usable": False}
            for source in SOURCES
        }
        report = build_public_ahead_report(
            lat=52.4000,
            lon=16.9250,
            heading=37.0,
            health=health,
        )
        self.assertEqual(
            report["answer_state"],
            "no_verified_public_snapshot_ahead",
        )
        self.assertEqual(report["selected"], [])
        self.assertEqual(report["vision_requests"], [])

    def test_healthy_camera_behind_is_not_selected(self):
        health = {
            "webcamera:poznan-stary-rynek": {"usable": True},
        }
        report = build_public_ahead_report(
            lat=52.4000,
            lon=16.9250,
            heading=217.0,
            health=health,
            max_distance_m=3000,
        )
        self.assertEqual(report["selected"], [])

    def test_nearby_owner_scan_is_local_and_identity_free(self):
        health = {
            "lookcam:poznan-hetmanska": {"usable": True},
        }
        report = build_public_nearby_report(
            lat=52.3905,
            lon=16.8942,
            health=health,
        )
        self.assertEqual(report["answer_state"], "ready_for_vision")
        self.assertLessEqual(report["selected_radius_m"], 500.0)
        self.assertEqual(report["selected"][0]["source_id"], "lookcam:poznan-hetmanska")
        task = report["vision_requests"][0]["task"].lower()
        self.assertIn("do not identify", task)
        self.assertIn("possible candidate", task)

    def test_vision_request_forbids_identity_task(self):
        health = {
            "webcamera:poznan-stary-rynek": {"usable": True},
        }
        report = build_public_ahead_report(
            lat=52.4000,
            lon=16.9250,
            heading=37.0,
            health=health,
            max_distance_m=3000,
        )
        task = report["vision_requests"][0]["task"].lower()
        self.assertIn("do not identify people", task)


if __name__ == "__main__":
    unittest.main()
