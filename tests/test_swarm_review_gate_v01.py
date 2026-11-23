import copy
import unittest

from src.swarm_review_gate_v01 import assess, assess_external_advice, safe_repo_path


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

    def test_sensitive_file_paths_are_rejected(self):
        for path in (
            "src/secrets.json",
            "src/Secrets.json",
            "src/credentials.yaml",
            "src/token.py",
            "docs/api_key.md",
            "src/nested/SECRET.backup.py",
            "examples/config/.ENV.local",
            "src/secret/key.txt",
            "tests/TOKEN/ok.py",
        ):
            with self.subTest(path=path):
                self.assertFalse(safe_repo_path(path))

    def test_safe_source_paths_still_accepted(self):
        for path in (
            "src/safe_rules.py",
            "tests/test_example.py",
            "docs/api_reference.md",
            "examples/hello.json",
            "src/secure_notes.py",
        ):
            with self.subTest(path=path):
                self.assertTrue(safe_repo_path(path))

    def test_secret_path_in_manifest_holds(self):
        data = valid_manifest()
        data["changed_paths"] = ["src/secrets.json"]
        self.assertIn("unsafe_changed_path", assess(data)["errors"])

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



def valid_external_ticket_and_report():
    ticket = {
        "schema": "JARVIS_SWARM_TICKET/0.1",
        "task_id": "lab-external-review-001",
        "repository": "example/jarvis-lab",
        "base_sha": "a" * 40,
        "visibility": "PUBLIC",
        "role": "reviewer",
        "allowed_paths": ["src/swarm_review_gate_v01.py"],
        "max_response_chars": 1000,
    }
    report = {
        "schema": "JARVIS_SWARM_EXTERNAL_ADVICE/0.1",
        "task_id": ticket["task_id"],
        "repository": ticket["repository"],
        "base_sha": ticket["base_sha"],
        "role": "reviewer",
        "provider": "deepwiki-mcp",
        "paths": ["src/swarm_review_gate_v01.py"],
        "advice": "Suggest a negative test for nested secret-like folder names.",
    }
    return ticket, report


class ExternalAgentContractTests(unittest.TestCase):
    def test_valid_external_report_remains_quarantined(self):
        ticket, report = valid_external_ticket_and_report()
        result = assess_external_advice(ticket, report)
        self.assertEqual(result["verdict"], "QUARANTINED_ADVISORY_ONLY")
        self.assertFalse(result["merge_allowed"])
        self.assertFalse(result["commit_allowed"])
        self.assertFalse(result["execute_generated_code"])
        self.assertFalse(result["provider_identity_verified"])

    def test_wrong_commit_or_task_holds(self):
        for field, altered in (("base_sha", "b" * 40),
                               ("task_id", "lab-other-task-001")):
            with self.subTest(field=field):
                t, r = valid_external_ticket_and_report()
                r[field] = altered
                self.assertEqual(assess_external_advice(t, r)["verdict"], "HOLD")

    def test_private_request_holds(self):
        t, r = valid_external_ticket_and_report()
        t["visibility"] = "PRIVATE"
        self.assertIn("public_only", assess_external_advice(t, r)["errors"])

    def test_external_cannot_request_direct_merge(self):
        t, r = valid_external_ticket_and_report()
        r["auto_merge"] = True
        self.assertIn("unsupported_report_fields", assess_external_advice(t, r)["errors"])

    def test_external_cannot_forge_test_receipt(self):
        t, r = valid_external_ticket_and_report()
        r["tests_passed"] = 999
        self.assertEqual(assess_external_advice(t, r)["verdict"], "HOLD")

    def test_out_of_scope_and_sensitive_paths_hold(self):
        for path in ("src/secrets.json", "src/another.py",
                     "src/../private.json", "/etc/passwd"):
            with self.subTest(path=path):
                t, r = valid_external_ticket_and_report()
                r["paths"] = [path]
                self.assertIn("out_of_scope_or_unsafe_path",
                              assess_external_advice(t, r)["errors"])

    def test_large_advice_holds(self):
        t, r = valid_external_ticket_and_report()
        r["advice"] = "x" * 1100
        self.assertIn("missing_or_oversize_advice",
                      assess_external_advice(t, r)["errors"])

    def test_unhashable_or_invalid_paths_fail_closed(self):
        t, r = valid_external_ticket_and_report()
        t["allowed_paths"] = [{"not": "a path"}]
        self.assertEqual(assess_external_advice(t, r)["verdict"], "HOLD")
        t, r = valid_external_ticket_and_report()
        r["paths"] = [{"not": "a path"}]
        self.assertEqual(assess_external_advice(t, r)["verdict"], "HOLD")

    def test_missing_report_fails_closed(self):
        t, _ = valid_external_ticket_and_report()
        self.assertEqual(assess_external_advice(t, None)["verdict"], "HOLD")

    def test_does_not_modify_external_payload(self):
        t, r = valid_external_ticket_and_report()
        orig = copy.deepcopy((t, r))
        assess_external_advice(t, r)
        self.assertEqual((t, r), orig)


if __name__ == "__main__":
    unittest.main()
