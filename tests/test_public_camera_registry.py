import unittest

from src.public_camera_registry import SOURCES, snapshot_camera_records


class PublicCameraRegistryTests(unittest.TestCase):
    def test_registry_ids_are_unique(self):
        ids = [s.source_id for s in SOURCES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_only_runtime_healthy_snapshots_are_promoted(self):
        rows = snapshot_camera_records(
            SOURCES,
            healthy_ids={"webcamera:poznan-stary-rynek", "video-poznan:mtp-602"},
        )
        self.assertEqual(
            [r.camera_id for r in rows],
            ["webcamera:poznan-stary-rynek"],
        )
        self.assertIsNone(rows[0].observed_at)

    def test_public_boundary(self):
        self.assertTrue(all(s.public for s in SOURCES))


if __name__ == "__main__":
    unittest.main()
