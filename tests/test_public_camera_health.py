import unittest

from src.public_camera_health import snapshot_freshness


class PublicCameraHealthTests(unittest.TestCase):
    def test_recent_last_modified_is_verified(self):
        result = snapshot_freshness(
            last_modified="Wed, 28 Oct 2026 10:08:32 GMT",
            now_ts=1793182255.0,
            max_stale_s=1800,
        )
        self.assertTrue(result["verified"])
        self.assertEqual(result["reason"], "within_max_stale")

    def test_old_snapshot_is_rejected_even_if_http_would_be_200(self):
        result = snapshot_freshness(
            last_modified="Tue, 10 Feb 2026 22:40:40 GMT",
            now_ts=1793182255.0,
            max_stale_s=1800,
        )
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "stale_last_modified")

    def test_missing_freshness_evidence_is_rejected(self):
        result = snapshot_freshness(
            last_modified=None,
            now_ts=1793182255.0,
            max_stale_s=1800,
        )
        self.assertFalse(result["verified"])
        self.assertEqual(
            result["reason"],
            "last_modified_missing_or_invalid",
        )


if __name__ == "__main__":
    unittest.main()
