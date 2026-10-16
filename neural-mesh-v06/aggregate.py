#!/usr/bin/env python3
"""GENESIS Neural Mesh LAB v0.6 strict distributed result verifier."""
import hashlib
import json
from pathlib import Path

MODEL = "f156378799b6a67ae8e6c754f00e302785fcc130fa914d4c830747655aaa7e00"
WEIGHTS = "674a35040841dc2b7bb7e227327a78ffa4a3c9a03fd16d0fd24cebb5eadf1577"
EXPECTED = {
    (0, 128): "6a1fddeaf716336a9aea024f045c91ac2efb558062baf5586fc5288f39981813",
    (128, 256): "3d4c1485e1a5f20489654a3710030e7b0a3292f6de559640f67685bf660d348e",
}
FULL_SHA = "42ba48a98917fb299da54e1ca078b574e32d3e2fa59c1585942129e85ae9155f"

def validate(doc, bounds):
    assert isinstance(doc, dict), "BAD_DOCUMENT"
    assert doc.get("schema") == "GENESIS_NEURAL_MESH_PARALLEL/0.6", "BAD_SCHEMA"
    assert (doc.get("start"), doc.get("end")) == bounds, "WRONG_RANGE"
    assert doc.get("cases") == bounds[1] - bounds[0], "BAD_SIZE"
    assert doc.get("repetitions") == 80000, "BAD_REPS"
    assert doc.get("model_npz_sha256") == MODEL, "BAD_MODEL"
    assert doc.get("packed_weights_sha256") == WEIGHTS, "BAD_WEIGHTS"
    data = bytes.fromhex(doc["predictions_hex"])
    assert len(data) == bounds[1] - bounds[0] and set(data) <= {0, 1}, "BAD_OUTPUT"
    assert hashlib.sha256(data).hexdigest() == doc["prediction_sha256"] == EXPECTED[bounds], "BAD_HASH"
    assert sum(data) == doc["positive_count"], "BAD_POSITIVES"
    assert isinstance(doc.get("compute_ms"), (float, int)) and doc["compute_ms"] > 0, "BAD_DURATION"
    assert isinstance(doc.get("runner_name"), str) and doc["runner_name"], "BAD_RUNNER"
    return data

def main():
    root = Path("artifacts")
    left = json.loads((root / "mesh-left" / "result.json").read_text())
    right = json.loads((root / "mesh-right" / "result.json").read_text())
    a = validate(left, (0, 128))
    b = validate(right, (128, 256))
    assert left["runner_name"] != right["runner_name"], "RUNNER_COLLISION"
    assert hashlib.sha256(a + b).hexdigest() == FULL_SHA, "WRONG_MERGE"
    result = {
        "verdict": "PASS_TWO_PARALLEL_GITHUB_HOSTED_NODES",
        "cases": 256, "repetitions": 80000, "positive_count": sum(a+b),
        "predictions_sha256": FULL_SHA,
        "max_shard_compute_ms": max(left["compute_ms"], right["compute_ms"]),
        "runner_names": [left["runner_name"], right["runner_name"]],
        "e2e_speedup": "REQUIRES_GITHUB_JOB_TIMELINE",
    }
    Path("merge_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("GENESIS_NEURAL_MESH_V06_MERGE " + json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
