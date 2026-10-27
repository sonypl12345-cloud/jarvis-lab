import unittest
from urllib.error import HTTPError

from src.gddkia_camera_adapter import (
    GDDKiAAccessError,
    _image_url,
    fetch_camerapoints_payload,
    parse_camerapoints,
)


class GDDKiAAdapterTests(unittest.TestCase):
    def test_parses_nested_real_kpd_shape(self):
        payload = {
            "response": {
                "response": [
                    {
                        "id": 101,
                        "latitude": 52.4,
                        "longitude": 16.9,
                        "name": "Test point",
                        "road_number": "S11",
                        "mileage": 12.3,
                        "cameras": [
                            {
                                "id": 7,
                                "images": [
                                    {
                                        "path": "/camera/a.jpg",
                                        "updated_date": "2026-10-27T10:00:00+01:00",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        }
        rows = parse_camerapoints(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].camera_id, "gddkia:101:7")
        self.assertEqual(rows[0].name, "Test point")
        self.assertEqual(rows[0].lat, 52.4)
        self.assertEqual(rows[0].lon, 16.9)
        self.assertTrue(rows[0].image_url.endswith("/camera/a.jpg"))
        self.assertIsNotNone(rows[0].observed_at)

    def test_selects_newest_image(self):
        payload = [
            {
                "id": "x",
                "latitude": 52.4,
                "longitude": 16.9,
                "cameras": [
                    {
                        "images": [
                            {
                                "path": "/old.jpg",
                                "updated_date": "2026-10-27T08:00:00+01:00",
                            },
                            {
                                "path": "/new.jpg",
                                "updated_date": "2026-10-27T09:00:00+01:00",
                            },
                        ]
                    }
                ],
            }
        ]
        row = parse_camerapoints(payload)[0]
        self.assertTrue(row.image_url.endswith("/new.jpg"))

    def test_relative_and_absolute_image_urls(self):
        self.assertEqual(
            _image_url("/foo.jpg"),
            "https://kpd.gddkia.gov.pl/foo.jpg",
        )
        self.assertEqual(
            _image_url("https://example.test/x.jpg"),
            "https://example.test/x.jpg",
        )

    def test_missing_image_is_skipped_by_default(self):
        payload = [
            {
                "id": "x",
                "latitude": 52.4,
                "longitude": 16.9,
                "road_number": "92",
                "mileage": 10.0,
                "cameras": [],
            }
        ]
        self.assertEqual(parse_camerapoints(payload), [])
        rows = parse_camerapoints(payload, include_without_image=True)
        self.assertEqual(rows[0].name, "92 • 10.0 km")

    def test_bad_coordinates_are_ignored(self):
        payload = [{"id": 1, "latitude": "bad", "longitude": 16.9, "cameras": []}]
        self.assertEqual(parse_camerapoints(payload, include_without_image=True), [])

    def test_401_is_not_bypassed(self):
        class FakeOpener:
            def open(self, request, timeout=None):
                raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)

        with self.assertRaises(GDDKiAAccessError):
            fetch_camerapoints_payload(opener=FakeOpener())


if __name__ == "__main__":
    unittest.main()
