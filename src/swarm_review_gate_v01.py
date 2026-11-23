"""Advisory-only gate for reviewing contributions from multiple coding agents.

This tool does not run untrusted code, call models, push, merge, or deploy.
The supplied JSON is untrusted self-reporting: GitHub CI and owner review
must independently validate all claims before anything reaches main.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import PurePosixPath
from typing import Any

SCHEMA = "JARVIS_SWARM_PR_LAB/0.1"
REQUIRED_ROLES = ("planner", "coder", "tester", "reviewer")
SHA = re.compile(r"^[0-9a-fA-F]{40}$")
IDENT = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,79}$")
REPO = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
ALLOWED_ROOTS = {"src", "tests", "docs", "examples"}
SENSITIVE_NAME_STEMS = frozenset({"secret", "secrets", "credential",
                                  "credentials", "token", "tokens", "api_key"})


def safe_repo_path(value: Any) -> bool:
    """Only relative, canonical source/test/docs paths are candidates."""
    if not isinstance(value, str) or not value or len(value) > 240:
        return False
    if "\\" in value or "\x00" in value or value.startswith("/"):
        return False
    parts = value.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return False
    path = PurePosixPath(value)
    if str(path) != value or len(parts) < 2:
        return False
    if parts[0] not in ALLOWED_ROOTS:
        return False
    # Screen all path components, not just the final file's extension.
    # This is a defense-in-depth name filter, not a secrets scanner.
    if any(
        part.casefold().startswith(".env")
        or part.casefold().split(".", 1)[0] in SENSITIVE_NAME_STEMS
        for part in parts[1:]
    ):
        return False
    if path.suffix.lower() in {
        ".pem", ".key", ".p12", ".pfx", ".sqlite", ".db"
    }:
        return False
    return True



def assess_external_advice(ticket: Any, report: Any) -> dict[str, Any]:
    """Screen an external agent's suggestion without granting any code authority.

    Both payloads are untrusted *unless* the host independently binds the
    ticket to a real Git commit. Even a passing report stays quarantined.
    """
    errors: list[str] = []
    if not isinstance(ticket, dict) or not isinstance(report, dict):
        errors.append("ticket_or_report_not_object")
        return _external_result(errors)
    if ticket.get("schema") != "JARVIS_SWARM_TICKET/0.1":
        errors.append("invalid_ticket_schema")
    if report.get("schema") != "JARVIS_SWARM_EXTERNAL_ADVICE/0.1":
        errors.append("invalid_report_schema")
    if ticket.get("visibility") != "PUBLIC":
        errors.append("public_only")
    if not isinstance(ticket.get("task_id"), str) or not IDENT.fullmatch(
        ticket["task_id"]
    ):
        errors.append("invalid_task_id")
    if not isinstance(ticket.get("repository"), str) or not REPO.fullmatch(
        ticket["repository"]
    ):
        errors.append("invalid_repository")
    if not isinstance(ticket.get("base_sha"), str) or not SHA.fullmatch(
        ticket["base_sha"]
    ):
        errors.append("invalid_base_sha")
    if ticket.get("role") not in REQUIRED_ROLES:
        errors.append("invalid_ticket_role")
    if report.get("role") not in REQUIRED_ROLES:
        errors.append("invalid_report_role")

    for key in ("task_id", "repository", "base_sha", "role"):
        if ticket.get(key) != report.get(key):
            errors.append("mismatch:" + key)

    allowed = ticket.get("allowed_paths")
    changed = report.get("paths")
    if not isinstance(allowed, list) or not (1 <= len(allowed) <= 10):
        errors.append("invalid_ticket_paths")
        allowed = []
    elif any(not safe_repo_path(p) for p in allowed):
        errors.append("unsafe_ticket_path")
        allowed = []
    if not isinstance(changed, list) or not (1 <= len(changed) <= 10):
        errors.append("invalid_report_paths")
    elif (
        any(not safe_repo_path(p) for p in changed)
        or not set(changed).issubset(set(allowed))
    ):
        errors.append("out_of_scope_or_unsafe_path")

    provider = report.get("provider")
    if not isinstance(provider, str) or not IDENT.fullmatch(provider):
        errors.append("invalid_provider_label")
    limit = ticket.get("max_response_chars")
    if type(limit) is not int or not (1 <= limit <= 4000):
        errors.append("invalid_response_budget")
        limit = 0
    advice = report.get("advice")
    if not isinstance(advice, str) or not (1 <= len(advice) <= limit):
        errors.append("missing_or_oversize_advice")
    elif "\x00" in advice:
        errors.append("invalid_advice_text")

    allowed_fields = {
        "schema", "task_id", "repository", "base_sha", "role",
        "provider", "paths", "advice"
    }
    if set(report) - allowed_fields:
        errors.append("unsupported_report_fields")
    return _external_result(errors)


def _external_result(errors: list[str]) -> dict[str, Any]:
    return {
        "schema": "JARVIS_SWARM_EXTERNAL_ADVICE_GATE/0.1",
        "verdict": "HOLD" if errors else "QUARANTINED_ADVISORY_ONLY",
        "errors": sorted(set(errors)),
        "merge_allowed": False,
        "commit_allowed": False,
        "execute_generated_code": False,
        "provider_identity_verified": False,
        "next": "Verify GitHub source/commit and independently test any proposed patch",
    }


def assess(manifest: Any) -> dict[str, Any]:
    """Screen a proposed change; NEVER return authority to merge."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return _result(["manifest_not_object"])

    if manifest.get("schema") != SCHEMA:
        errors.append("unsupported_schema")
    if not isinstance(manifest.get("task_id"), str) or not IDENT.fullmatch(
        manifest.get("task_id", "")
    ):
        errors.append("invalid_task_id")
    if not isinstance(manifest.get("repository"), str) or not REPO.fullmatch(
        manifest.get("repository", "")
    ):
        errors.append("invalid_repository")

    base = manifest.get("base_sha")
    head = manifest.get("head_sha")
    if not isinstance(base, str) or not SHA.fullmatch(base):
        errors.append("invalid_base_sha")
    if not isinstance(head, str) or not SHA.fullmatch(head):
        errors.append("invalid_head_sha")
    if isinstance(base, str) and isinstance(head, str) and base.lower() == head.lower():
        errors.append("unchanged_head")

    if manifest.get("mode") != "LAB_ONLY":
        errors.append("lab_only_required")
    if manifest.get("production_change") is not False:
        errors.append("production_changes_forbidden")
    if manifest.get("secret_data") is not False:
        errors.append("secret_data_forbidden")

    paths = manifest.get("changed_paths")
    if not isinstance(paths, list) or not (1 <= len(paths) <= 30):
        errors.append("invalid_changed_paths")
    elif any(not safe_repo_path(p) for p in paths):
        errors.append("unsafe_changed_path")
    elif len(set(paths)) != len(paths):
        errors.append("duplicate_changed_path")

    roles = manifest.get("roles")
    if not isinstance(roles, dict):
        errors.append("roles_required")
        roles = {}
    role_ids = []
    for role in REQUIRED_ROLES:
        val = roles.get(role)
        if not isinstance(val, str) or not IDENT.fullmatch(val):
            errors.append("missing_or_invalid_role:" + role)
        else:
            role_ids.append(val)
    if len(role_ids) != len(set(role_ids)):
        errors.append("role_sessions_not_distinct")

    receipts = manifest.get("tests")
    if not isinstance(receipts, list) or not (1 <= len(receipts) <= 20):
        errors.append("test_receipts_required")
    else:
        for receipt in receipts:
            if not isinstance(receipt, dict):
                errors.append("invalid_test_receipt")
                continue
            if (not isinstance(receipt.get("name"), str)
                    or not IDENT.fullmatch(receipt["name"])):
                errors.append("invalid_test_name")
            if receipt.get("verdict") != "PASS":
                errors.append("test_not_pass")
            if receipt.get("head_sha") != head:
                errors.append("test_head_mismatch")
            if receipt.get("worker_id") != roles.get("tester"):
                errors.append("test_worker_mismatch")

    review = manifest.get("review")
    if not isinstance(review, dict):
        errors.append("review_required")
    else:
        if review.get("verdict") != "APPROVE":
            errors.append("review_not_approved")
        if review.get("head_sha") != head:
            errors.append("review_head_mismatch")
        if review.get("worker_id") != roles.get("reviewer"):
            errors.append("review_worker_mismatch")
    return _result(errors)


def _result(errors: list[str]) -> dict[str, Any]:
    return {
        "schema": "JARVIS_SWARM_GATE_RESULT/0.1",
        "verdict": "HOLD" if errors else "CANDIDATE_NEEDS_EXTERNAL_CHECKS",
        "errors": sorted(set(errors)),
        "merge_allowed": False,
        "production_authority": False,
        "trust": "UNTRUSTED_MANIFEST",
        "next": "Verify actual GitHub diff, independent CI status, and owner approval",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Screen a swarm code-change manifest.")
    parser.add_argument("manifest", help="Local JSON manifest (max 128 KiB)")
    args = parser.parse_args()
    try:
        with open(args.manifest, "rb") as f:
            raw = f.read(131073)
        if len(raw) > 131072:
            raise ValueError("manifest_too_large")
        decision = assess(json.loads(raw.decode("utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        decision = _result(["manifest_unreadable:" + type(exc).__name__])
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if decision["verdict"] == "CANDIDATE_NEEDS_EXTERNAL_CHECKS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
