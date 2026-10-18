"""Repeatable local retrieval evaluation for the pinned v16 development corpus."""

import json
from pathlib import Path

from frappe_knowledge.api import get_context

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def run_suite(snapshot, suite="heldout"):
	"""Run fixed questions as the current authorized site user; no model or web calls."""
	if suite not in {"development", "heldout", "validation"}:
		raise ValueError("Unknown retrieval suite")
	cases = json.loads((FIXTURES / f"retrieval-{suite}-v16.json").read_text(encoding="utf-8"))
	results = []
	for case in cases:
		context = get_context(snapshot, case["question"], max_chars=16000)
		paths = [(match["app"], match["path"]) for match in context.get("source_matches", [])]
		expected = (case["expected_app"], case["expected_path"])
		position = paths.index(expected) + 1 if expected in paths else None
		results.append(
			{
				"question": case["question"],
				"expected": expected,
				"rank": position,
				"top_paths": paths[:5],
				"within_budget": context.get("characters", 0) <= 16000,
			}
		)
	return {
		"snapshot": snapshot,
		"suite": suite,
		"queries": len(results),
		"source_recall_at_5": sum(item["rank"] is not None and item["rank"] <= 5 for item in results),
		"source_recall_at_1": sum(item["rank"] == 1 for item in results),
		"results": results,
	}


def run_held_out(snapshot):
	return run_suite(snapshot, "heldout")
