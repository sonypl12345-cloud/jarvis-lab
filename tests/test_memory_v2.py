import copy
import unittest

from src.jarvis_memory_v2 import consolidate, query


class MemoryV2Tests(unittest.TestCase):
    def test_raw_records_are_not_modified(self):
        records = [{"text": "A durable checkpoint preserves session continuity.", "source": "notes.md"}]
        original = copy.deepcopy(records)
        consolidate(records)
        self.assertEqual(records, original)

    def test_exact_duplicates_merge_with_sources(self):
        records = [
            {"text": "Verify every external action before recording success.", "source": "a.md", "confidence": 0.9},
            {"text": "Verify every external action before recording success.", "source": "b.md", "confidence": 0.8},
        ]
        index = consolidate(records)
        self.assertEqual(index["stats"]["facts"], 1)
        self.assertEqual(index["stats"]["duplicates_merged"], 1)
        self.assertEqual(index["facts"][0]["supporting_sources"], ["b.md"])

    def test_query_prefers_relevant_fact(self):
        index = consolidate(
            [
                {"text": "DOM snapshots need a freshness TTL before browser actions.", "source": "dom.md", "confidence": 0.9},
                {"text": "Memory facts retain their original source.", "source": "memory.md", "confidence": 0.9},
            ]
        )
        hits = query(index, "browser DOM freshness", limit=1)
        self.assertEqual(hits[0]["source"], "dom.md")


if __name__ == "__main__":
    unittest.main()
