import unittest

from src.what_ahead import build_ahead_report


class WhatAheadTests(unittest.TestCase):
    def test_end_to_end_selects_forward_public_camera(self):
        now = 1_798_000_000.0
        snapshot = {
            "mode": "read_only_public_kpd_camera_layer",
            "snapshot_id": "abc",
            "captured_at": "2026-10-28T09:00:00+00:00",
            "points": [
                {
                    "id": "north",
                    "latitude": 52.4100,
                    "longitude": 16.9000,
                    "name": "Ahead",
                    "road_number": "S11",
                    "mileage": 10.0,
                    "cameras": [
                        {
                            "id": "1",
                            "images": [
                                {
                                    "path": "/camera/ahead.jpg",
                                    # No offset: parser deliberately won't
                                    # invent timezone/freshness.
                                    "updated_date": "2026-10-28T10:00:00",
                                }
                            ],
                        }
                    ],
                },
                {
                    "id": "south",
                    "latitude": 52.3900,
                    "longitude": 16.9000,
                    "name": "Behind",
                    "road_number": "S11",
                    "mileage": 9.0,
                    "cameras": [
                        {
                            "id": "2",
                            "images": [
                                {
                                    "path": "/camera/behind.jpg",
                                    "updated_date": "2026-10-28T10:00:00",
                                }
                            ],
                        }
                    ],
                },
            ],
        }
        report = build_ahead_report(
            snapshot,
            lat=52.4000,
            lon=16.9000,
            heading=0.0,
            max_distance_m=3000,
            now_ts=now,
        )
        self.assertEqual(report["answer_state"], "ready_for_vision")
        self.assertEqual(report["selected_count"], 1)
        self.assertEqual(report["selected"][0]["name"], "Ahead")
        self.assertTrue(report["selected"][0]["image_url"].endswith("/camera/ahead.jpg"))

    def test_requires_sanitized_public_snapshot(self):
        with self.assertRaises(ValueError):
            build_ahead_report(
                {"mode": "something_else", "points": []},
                lat=52.4,
                lon=16.9,
                heading=0,
            )

    def test_no_camera_ahead_is_explicit(self):
        snapshot = {
            "mode": "read_only_public_kpd_camera_layer",
            "snapshot_id": "none",
            "points": [],
        }
        report = build_ahead_report(
            snapshot,
            lat=52.4,
            lon=16.9,
            heading=90,
        )
        self.assertEqual(report["answer_state"], "no_public_camera_ahead")
        self.assertEqual(report["selected"], [])


if __name__ == "__main__":
    unittest.main()
