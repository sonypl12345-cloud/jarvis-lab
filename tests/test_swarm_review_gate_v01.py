import copy
import unittest

from src.swarm_review_gate_v01 import assess, safe_repo_path


BASE = "a" * 40
HEAD = "b" * 40


def valid_manifest():
    return {
        "schema": "JARVIS_SWARM_PR_LAB/0.1",
        "task_id": "lab-example-001",
        "repository": "example/jarvis-lab",
        "base_sha": BASE,
        "head_sha": HEAD,
        "mode": "LAB_ONLY",
        "production_change": False,
        "secret_data": False,
        "changed_paths": ["src/example.py", "tests/test_example.py"],
        "roles": {
            "planner": "planner-session-1",
            "coder": "coder-session-2",
            "tester": "tester-session-3",
            "reviewer": "reviewer-session-4",
        },
        "tests": [
            {
                "name": "unit-tests",
                "verdict": "PASS",
                "head_sha": HEAD,
                "worker_id": "tester-session-3",
            }
        ],
        "review": {
            "verdict": "APPROVE",
            "head_sha": HEAD,
            "worker_id": "reviewer-session-4",
        },
    }


class SwarmReviewGateTests(unittest.TestCase):
    def test_valid_pilot_is_only_a_candidate(self):
        result = assess(valid_manifest())
        self.assertEqual(result["verdict"], "CANDIDATE_NEEDS_EXTERNAL_CHECKS")
        self.assertFalse(result["merge_allowed"])
        self.assertFalse(result["production_authority"])

    def test_different_head_required(self):
        data = valid_manifest()
        data["head_sha"] = BASE
        self.assertIn("unchanged_head", assess(data)["errors"])

    def test_reviewer_must_be_separate_session(self):
        data = valid_manifest()
        data["roles"]["reviewer"] = data["roles"]["coder"]
        self.assertIn("role_sessions_not_distinct", assess(data)["errors"])

    def test_stale_test_receipt_holds(self):
        data = valid_manifest()
        data["tests"][0]["head_sha"] = BASE
        self.assertIn("test_head_mismatch", assess(data)["errors"])

    def test_stale_review_holds(self):
        data = valid_manifest()
        data["review"]["head_sha"] = BASE
        self.assertIn("review_head_mismatch", assess(data)["errors"])

    def test_test_failure_holds(self):
        data = valid_manifest()
        data["tests"][0]["verdict"] = "FAIL"
        self.assertIn("test_not_pass", assess(data)["errors"])

    def test_production_change_holds(self):
        data = valid_manifest()
        data["production_change"] = True
        self.assertIn("production_changes_forbidden", assess(data)["errors"])

    def test_missing_explicit_false_secrets_holds(self):
        data = valid_manifest()
        del data["secret_data"]
        self.assertIn("secret_data_forbidden", assess(data)["errors"])

    def test_path_traversal_holds(self):
        for path in ("src/../secret.txt", "/etc/passwd", "src\\evil.py",
                     ".github/workflows/unsafe.yml", "src/.env", "src/key.pem"):
            with self.subTest(path=path):
                self.assertFalse(safe_repo_path(path))

    def test_duplicate_paths_hold(self):
        data = valid_manifest()
        data["changed_paths"].append("src/example.py")
        self.assertIn("duplicate_changed_path", assess(data)["errors"])

    def test_does_not_mutate_input(self):
        data = valid_manifest()
        before = copy.deepcopy(data)
        assess(data)
        self.assertEqual(before, data)

    def test_malformed_manifest_holds(self):
        for data in (None, [], {"schema": "wrong"}):
            self.assertEqual(assess(data)["verdict"], "HOLD")


if __name__ == "__main__":
    unittest.main()
