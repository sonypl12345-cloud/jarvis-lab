import unittest

from src.camera_ahead import (
    CameraRecord,
    angular_distance_deg,
    heading_from_points,
    select_cameras_ahead,
)


class CameraAheadTests(unittest.TestCase):
    def test_angular_wrap(self):
        self.assertAlmostEqual(angular_distance_deg(359, 1), 2)
        self.assertAlmostEqual(angular_distance_deg(10, 350), 20)

    def test_heading_requires_real_movement(self):
        self.assertIsNone(
            heading_from_points(52.400000, 16.900000, 52.400001, 16.900001)
        )
        heading = heading_from_points(52.400000, 16.900000, 52.401000, 16.900000)
        self.assertIsNotNone(heading)
        self.assertTrue(heading < 5 or heading > 355)

    def test_selects_forward_camera_and_rejects_behind(self):
        now = 1_000_000.0
        cams = [
            CameraRecord(
                "north",
                "North",
                52.4100,
                16.9000,
                "test",
                public=True,
                observed_at=now - 30,
            ),
            CameraRecord(
                "south",
                "South",
                52.3900,
                16.9000,
                "test",
                public=True,
                observed_at=now - 30,
            ),
        ]
        result = select_cameras_ahead(
            cams,
            lat=52.4000,
            lon=16.9000,
            heading=0,
            max_distance_m=3000,
            now_ts=now,
        )
        self.assertEqual([x.camera.camera_id for x in result], ["north"])

    def test_private_and_stale_are_rejected(self):
        now = 10_000.0
        cams = [
            CameraRecord(
                "private",
                "Private",
                52.4100,
                16.9000,
                "test",
                public=False,
                observed_at=now - 10,
            ),
            CameraRecord(
                "stale",
                "Stale",
                52.4090,
                16.9000,
                "test",
                public=True,
                observed_at=now - 5000,
            ),
        ]
        result = select_cameras_ahead(
            cams,
            lat=52.4000,
            lon=16.9000,
            heading=0,
            now_ts=now,
            stale_after_s=900,
        )
        self.assertEqual(result, [])

    def test_prefers_nearer_camera_when_angles_are_equal(self):
        cams = [
            CameraRecord("near", "Near", 52.405, 16.9000, "test"),
            CameraRecord("far", "Far", 52.420, 16.9000, "test"),
        ]
        result = select_cameras_ahead(
            cams,
            lat=52.4000,
            lon=16.9000,
            heading=0,
            max_distance_m=5000,
        )
        self.assertEqual(result[0].camera.camera_id, "near")


if __name__ == "__main__":
    unittest.main()
