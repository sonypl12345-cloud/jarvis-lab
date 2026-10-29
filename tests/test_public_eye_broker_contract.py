import pathlib
import unittest

SOURCE = pathlib.Path(
    "supabase/functions/genesis-camera-broker-lab-v01/index.ts"
).read_text(encoding="utf-8")


class PublicEyeBrokerContractTests(unittest.TestCase):
    def test_only_fixed_public_eye_id_families_are_resolved(self):
        self.assertIn(r"/^webcamera:([A-Za-z0-9._-]{1,180})$/", SOURCE)
        self.assertIn(r"/^argos:([0-9a-f]{18})$/", SOURCE)
        self.assertIn(
            '"https://imageserver.webcamera.pl/miniaturki/"+m[1]+".jpg"',
            SOURCE,
        )
        self.assertIn(
            '"https://argosatlas.com/api/cam/"+m[1]+"/image"',
            SOURCE,
        )

    def test_generic_public_eye_frame_is_ephemeral(self):
        self.assertIn('b.action==="public_eye_frame"', SOURCE)
        self.assertIn('"cache-control":"no-store"', SOURCE)
        self.assertIn('"x-genesis-persistence":"ephemeral-no-store"', SOURCE)
        self.assertIn("max_frame_bytes:2000000", SOURCE)

    def test_generic_vision_input_is_health_gated(self):
        self.assertIn("await publicEyeProbe(eye.eye_id)", SOURCE)
        self.assertIn('error:"public_eye_unavailable"', SOURCE)
        self.assertIn('action:"public_eye_frame"', SOURCE)

    def test_arbitrary_url_is_not_an_action_argument(self):
        self.assertNotIn("publicEyeFrame(b.url", SOURCE)
        self.assertNotIn("publicEyeProbe(b.url", SOURCE)


if __name__ == "__main__":
    unittest.main()
