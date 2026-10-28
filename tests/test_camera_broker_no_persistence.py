import pathlib
import unittest


class CameraBrokerNoPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = pathlib.Path(
            "supabase/functions/genesis-camera-broker-lab-v01/index.ts"
        ).read_text(encoding="utf-8")

    def test_raw_camera_media_is_ephemeral(self):
        self.assertIn('raw_images:"forbidden"', self.source)
        self.assertIn('video_segments:"forbidden"', self.source)
        self.assertIn('mode:"ephemeral_on_demand_only"', self.source)
        self.assertIn('"cache-control":"no-store"', self.source)
        self.assertIn('"x-genesis-persistence":"ephemeral-no-store"', self.source)

    def test_broker_contains_no_storage_upload_path(self):
        lower = self.source.lower()
        self.assertNotIn(".storage.", lower)
        self.assertNotIn("storage/v1/object", lower)
        self.assertNotIn(".upload(", lower)
        self.assertNotIn("data:image", lower)
        self.assertNotIn("base64", lower)

    def test_camera_media_is_not_inserted_into_database(self):
        lower = self.source.lower()
        self.assertNotIn("insert into", lower)
        self.assertNotIn("supabase.from(", lower)

    def test_persistence_actions_are_explicitly_denied(self):
        self.assertIn('"persist_frame"', self.source)
        self.assertIn('"save_frame"', self.source)
        self.assertIn('"archive_frame"', self.source)
        self.assertIn('"upload_frame"', self.source)
        self.assertIn("persistence_forbidden_by_policy", self.source)

    def test_frame_size_guard_exists(self):
        self.assertIn("max_frame_bytes:2000000", self.source)
        self.assertIn("frame_too_large", self.source)


if __name__ == "__main__":
    unittest.main()
