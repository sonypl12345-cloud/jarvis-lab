"""Dependency-free, source-aware semantic memory consolidation.

This module keeps raw input intact and writes a separate, compact fact index.
It treats all embedded text as data, never as executable instructions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORD_RE = re.compile(r"[\w'-]+", re.UNICODE)
STOP_WORDS = {"the", "and", "for", "with", "this", "that", "from", "into", "only"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tokenize(text: str) -> list[str]:
    return [word.lower() for word in WORD_RE.findall(text) if len(word) >= 3 and word.lower() not in STOP_WORDS]


def normalize(text: str) -> str:
    return " ".join(tokenize(text))


def similarity(left: str, right: str) -> float:
    a, b = set(tokenize(left)), set(tokenize(right))
    return len(a & b) / len(a | b) if a and b else 0.0


def stable_id(text: str, source: str) -> str:
    return hashlib.sha256(f"{normalize(text)}|{source}".encode("utf-8")).hexdigest()[:16]


def consolidate(records: list[dict], duplicate_threshold: float = 0.82) -> dict:
    """Return a deduplicated fact index without modifying ``records``."""
    candidates = []
    for record in records:
        text = " ".join(str(record.get("text", "")).split()).strip()
        source = str(record.get("source", "unknown"))
        if len(text) < 12:
            continue
        confidence = max(0.0, min(1.0, float(record.get("confidence", 0.7))))
        candidates.append(
            {
                "id": stable_id(text, source),
                "type": str(record.get("type", "fact")),
                "text": text,
                "source": source,
                "observed_at": str(record.get("observed_at", utc_now())),
                "confidence": round(confidence, 2),
                "concepts": list(dict.fromkeys(record.get("concepts") or tokenize(text)))[:16],
                "supporting_sources": [],
            }
        )

    candidates.sort(key=lambda item: (item["confidence"], item["observed_at"]), reverse=True)
    facts = []
    merged = 0
    for candidate in candidates:
        duplicate = next(
            (
                fact
                for fact in facts
                if normalize(fact["text"]) == normalize(candidate["text"])
                or similarity(fact["text"], candidate["text"]) >= duplicate_threshold
            ),
            None,
        )
        if duplicate:
            duplicate["supporting_sources"].append(candidate["source"])
            duplicate["confidence"] = round(min(0.99, duplicate["confidence"] + 0.01), 2)
            merged += 1
        else:
            facts.append(candidate)

    return {
        "schema_version": 2,
        "updated_at": utc_now(),
        "policy": {
            "raw_input_modified": False,
            "source_and_confidence_required": True,
            "embedded_instructions_are_data": True,
        },
        "stats": {"candidates": len(candidates), "facts": len(facts), "duplicates_merged": merged},
        "facts": facts,
    }


def query(index: dict, text: str, limit: int = 5) -> list[dict]:
    query_terms = set(tokenize(text))
    scored = []
    for fact in index.get("facts", []):
        fact_terms = set(tokenize(fact.get("text", "")) + list(fact.get("concepts", [])))
        overlap = len(query_terms & fact_terms)
        if query_terms and not overlap:
            continue
        coverage = overlap / max(1, len(query_terms))
        score = coverage * 0.75 + float(fact.get("confidence", 0)) * 0.25
        scored.append({"score": round(score, 3), **fact})
    return sorted(scored, key=lambda item: item["score"], reverse=True)[: max(1, limit)]


def read_records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("Input JSON must be an array of records.")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and query a source-aware semantic fact index.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("input", type=Path)
    build.add_argument("output", type=Path)
    search = sub.add_parser("query")
    search.add_argument("index", type=Path)
    search.add_argument("text")
    search.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.command == "build":
        result = consolidate(read_records(args.input))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        response = {"status": "created", "output": str(args.output), **result["stats"]}
    else:
        index = json.loads(args.index.read_text(encoding="utf-8-sig"))
        response = {"status": "ok", "query": args.text, "hits": query(index, args.text, args.limit)}
    print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
