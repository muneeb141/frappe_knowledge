import contextlib
import copy
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from frappe_knowledge.cli import main
from frappe_knowledge.core.index import (
	SourceRoot,
	_canonical,
	_digest,
	build_snapshot,
	compare_snapshots,
	retrieve_context,
	validate_snapshot,
)
from frappe_knowledge.core.profiles import CompatibilityProfile, SourceApp, get_profile, validate_sources
from frappe_knowledge.core.source_chunks import MAX_CHUNK_CHARS, iter_source_chunks

FIXTURES = Path(__file__).parent / "fixtures" / "upstream"
HRMS = "2478afc7a8f4959d500f6d17522853f0d244e38f"
ERPNEXT = "5af6561f5aa48104559692fb4fd82f2580e8d338"


def sample():
	return build_snapshot(
		"v16-research",
		[
			SourceRoot("hrms", "frappe/hrms", HRMS, FIXTURES / "hrms", "16"),
			SourceRoot("erpnext", "frappe/erpnext", ERPNEXT, FIXTURES / "erpnext", "16"),
		],
	)


class IndexTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.snapshot = sample()

	def test_real_v16_payroll_reaches_erpnext_journal(self):
		self.assertTrue(
			any(
				e["relation"] == "USES_DOCTYPE"
				and e["source"].startswith("hrms:")
				and e["target"] == "erpnext:doctype:Journal Entry"
				for e in self.snapshot["edges"]
			)
		)
		self.assertTrue(
			next(n for n in self.snapshot["nodes"] if n["id"] == "erpnext:doctype:Journal Entry")["resolved"]
		)

	def test_real_controller_is_linked_to_doctype(self):
		self.assertTrue(
			any(
				e["relation"] == "CONTROLLER_FOR" and e["target"] == "hrms:doctype:Payroll Entry"
				for e in self.snapshot["edges"]
			)
		)
		self.assertTrue(
			any(
				e["relation"] == "CONTROLLER_MODULE_FOR" and e["target"] == "hrms:doctype:Payroll Entry"
				for e in self.snapshot["edges"]
			)
		)

	def test_source_authored_descriptions_and_relation_meanings_are_explicit(self):
		self.assertEqual(self.snapshot["schema_version"], 3)
		journal = next(n for n in self.snapshot["nodes"] if n["id"] == "erpnext:doctype:Journal Entry")
		self.assertEqual(
			journal["source_description"], "A direct entry in your books, for anything without its own form."
		)
		self.assertEqual(journal["description_status"], "source_declared_unverified")
		self.assertEqual(journal["description_evidence"]["start_line"], 7)
		slips = next(
			n for n in self.snapshot["nodes"] if n["title"] == "create_salary_slips" and n["kind"] == "symbol"
		)
		self.assertIn("Creates salary slip", slips["source_description"])
		pack = retrieve_context(self.snapshot, "v16-research", "Payroll Entry", max_chars=64000, max_nodes=50)
		self.assertIn("USES_DOCTYPE", pack["relation_meanings"])
		self.assertIn("does not prove", pack["relation_meanings"]["USES_DOCTYPE"])

	def test_legacy_profiled_snapshot_without_descriptions_still_validates(self):
		old = copy.deepcopy(self.snapshot)
		old["schema_version"] = 2
		for node in old["nodes"]:
			node.pop("source_description", None)
			node.pop("description_status", None)
			node.pop("description_evidence", None)
		old["snapshot_id"] = _digest(_canonical({k: v for k, v in old.items() if k != "snapshot_id"}))
		validate_snapshot(old, "v16-research", profile_id="frappe-v16")
		self.assertEqual(retrieve_context(old, "v16-research", "Payroll Entry")["schema_version"], 1)

	def test_build_is_deterministic(self):
		self.assertEqual(self.snapshot["snapshot_id"], sample()["snapshot_id"])

	def test_every_evidence_link_has_exact_commit(self):
		validate_snapshot(self.snapshot, "v16-research")
		for n in self.snapshot["nodes"]:
			if n.get("evidence"):
				self.assertIn(n["evidence"]["revision"], n["evidence"]["url"])

	def test_project_scope_cannot_be_changed_at_query_time(self):
		with self.assertRaisesRegex(ValueError, "project mismatch"):
			retrieve_context(self.snapshot, "another-customer", "Payroll Entry")

	def test_tamper_is_detected(self):
		changed = copy.deepcopy(self.snapshot)
		changed["nodes"][0]["title"] = "tampered"
		with self.assertRaisesRegex(ValueError, "integrity"):
			validate_snapshot(changed, "v16-research")

	def test_rehashed_external_url_is_rejected(self):
		changed = copy.deepcopy(self.snapshot)
		next(n for n in changed["nodes"] if n.get("evidence"))["evidence"]["url"] = "https://example.com/fake"
		changed["snapshot_id"] = _digest(_canonical({k: v for k, v in changed.items() if k != "snapshot_id"}))
		with self.assertRaisesRegex(ValueError, "Evidence"):
			validate_snapshot(changed, "v16-research")

	def test_context_obeys_hard_character_budget(self):
		for budget in (3000, 8000, 16000):
			pack = retrieve_context(self.snapshot, "v16-research", "Payroll Entry", max_chars=budget)
			self.assertLessEqual(len(_canonical(pack)), budget)
			self.assertEqual(pack["budget_unit"], "characters")

	def test_context_includes_cross_app_evidence(self):
		pack = retrieve_context(self.snapshot, "v16-research", "Payroll Entry", max_chars=64000, max_nodes=50)
		self.assertTrue(any(n["id"] == "erpnext:doctype:Journal Entry" for n in pack["nodes"]))

	def test_unknown_query_returns_no_invented_answer(self):
		self.assertEqual(retrieve_context(self.snapshot, "v16-research", "xyzunrelated")["nodes"], [])

	def test_dynamic_links_are_reported_as_unresolved(self):
		with tempfile.TemporaryDirectory() as folder:
			root = Path(folder)
			directory = root / "example" / "doctype" / "reference"
			directory.mkdir(parents=True)
			(directory / "reference.json").write_text(
				json.dumps(
					{
						"doctype": "DocType",
						"name": "Reference",
						"fields": [
							{"fieldname": "target", "fieldtype": "Dynamic Link", "options": "target_type"}
						],
					}
				)
			)
			result = build_snapshot("project", [SourceRoot("example", "example/app", "a" * 40, root)])
			self.assertTrue(
				any(i["reason"] == "dynamic_link_requires_runtime_resolution" for i in result["issues"])
			)
			self.assertEqual(result["edges"], [])

	def test_mutable_branch_is_rejected(self):
		with self.assertRaisesRegex(ValueError, "immutable"):
			build_snapshot("project", [SourceRoot("hrms", "frappe/hrms", "version-16", FIXTURES / "hrms")])

	def test_multiple_versions_of_same_app_cannot_mix(self):
		s = SourceRoot("hrms", "frappe/hrms", HRMS, FIXTURES / "hrms")
		with self.assertRaisesRegex(ValueError, "one source revision"):
			build_snapshot("project", [s, s])

	def test_indexing_never_executes_python(self):
		with tempfile.TemporaryDirectory() as folder:
			root = Path(folder)
			marker = root / "executed"
			(root / "unsafe.py").write_text(
				f"from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError('do not execute')\n"
			)
			build_snapshot("project", [SourceRoot("example", "example/app", "a" * 40, root)])
			self.assertFalse(marker.exists())

	def test_symlinked_source_is_excluded(self):
		with tempfile.TemporaryDirectory() as folder:
			root = Path(folder)
			(root / "real.py").write_text("def hello():\n    pass\n")
			(root / "alias.py").symlink_to(root / "real.py")
			result = build_snapshot("project", [SourceRoot("example", "example/app", "a" * 40, root)])
			self.assertEqual(len(result["files"]), 1)

	def test_changed_file_invalidates_its_previous_nodes(self):
		with tempfile.TemporaryDirectory() as folder:
			root = Path(folder)
			file = root / "code.py"
			file.write_text("def hello():\n    return 1\n")
			before = build_snapshot("project", [SourceRoot("example", "example/app", "a" * 40, root)])
			file.write_text("def hello():\n    return 2\n")
			after = build_snapshot("project", [SourceRoot("example", "example/app", "b" * 40, root)])
			diff = compare_snapshots(before, after, "project")
			self.assertEqual(diff["changed"], ["example:code.py"])
			self.assertTrue(diff["invalidate_nodes"])

	def test_source_budget_is_enforced(self):
		with self.assertRaisesRegex(ValueError, "Total source budget"):
			build_snapshot(
				"v16-research",
				[SourceRoot("hrms", "frappe/hrms", HRMS, FIXTURES / "hrms", "16")],
				max_total_bytes=10,
			)

	def test_source_chunks_are_bounded_and_cite_the_snapshot_file(self):
		sources = [
			SourceRoot("hrms", "frappe/hrms", HRMS, FIXTURES / "hrms", "16"),
			SourceRoot("erpnext", "frappe/erpnext", ERPNEXT, FIXTURES / "erpnext", "16"),
		]
		chunks = list(iter_source_chunks(self.snapshot, sources))
		self.assertTrue(chunks)
		self.assertTrue(all(len(chunk["content"]) <= MAX_CHUNK_CHARS for chunk in chunks))
		self.assertTrue(
			all(
				chunk["file_sha256"] == self.snapshot["files"][f"{chunk['app']}:{chunk['path']}"]
				for chunk in chunks
			)
		)
		self.assertTrue(any("create_salary_slips" in chunk["content"] for chunk in chunks))
		payroll_chunks = [chunk for chunk in chunks if chunk["path"].endswith("payroll_entry.py")]
		self.assertEqual(
			"".join(chunk["content"] for chunk in payroll_chunks),
			(FIXTURES / "hrms" / payroll_chunks[0]["path"]).read_text(),
		)

	def test_source_chunks_reject_changed_local_bytes(self):
		with tempfile.TemporaryDirectory() as folder:
			root = Path(folder)
			source_file = root / "code.py"
			source_file.write_text("def original():\n    pass\n")
			source = SourceRoot("example", "example/app", "a" * 40, root)
			snapshot = build_snapshot("project", [source])
			source_file.write_text("def modified():\n    pass\n")
			with self.assertRaisesRegex(ValueError, "changed"):
				list(iter_source_chunks(snapshot, [source]))

	def test_new_snapshot_binds_the_active_profile(self):
		self.assertEqual(self.snapshot["profile_id"], "frappe-v16")
		with self.assertRaisesRegex(ValueError, "profile mismatch"):
			validate_snapshot(self.snapshot, "v16-research", profile_id="frappe-v15")
		with self.assertRaisesRegex(ValueError, "unavailable"):
			build_snapshot(
				"v16-research",
				[SourceRoot("hrms", "frappe/hrms", HRMS, FIXTURES / "hrms", "16")],
				profile_id="frappe-v15",
			)

	def test_legacy_snapshot_keeps_its_v16_identity(self):
		old = copy.deepcopy(self.snapshot)
		old["schema_version"] = 1
		del old["profile_id"]
		old["snapshot_id"] = _digest(_canonical({k: v for k, v in old.items() if k != "snapshot_id"}))
		validate_snapshot(old, "v16-research", profile_id="frappe-v16")
		self.assertEqual(retrieve_context(old, "v16-research", "Payroll Entry")["profile_id"], "frappe-v16")

	def test_app_registry_can_add_a_differently_versioned_custom_app(self):
		profile = CompatibilityProfile("frappe-v16", "16", (SourceApp("custom_pay", "team/custom_pay", "3"),))
		registry = {profile.name: profile}
		validate_sources(
			"frappe-v16",
			[{"app": "custom_pay", "repository": "team/custom_pay", "version": "3.2.1"}],
			registry=registry,
		)
		with self.assertRaisesRegex(ValueError, "incompatible"):
			validate_sources(
				"frappe-v16",
				[{"app": "custom_pay", "repository": "team/custom_pay", "version": "4.0"}],
				registry=registry,
			)

	def test_unregistered_and_wrong_major_sources_are_rejected(self):
		with self.assertRaisesRegex(ValueError, "incompatible"):
			validate_sources("frappe-v16", [{"app": "hrms", "repository": "frappe/hrms", "version": "15.0"}])
		with self.assertRaisesRegex(ValueError, "unavailable"):
			validate_sources("frappe-v16", [{"app": "other", "repository": "team/other", "version": "1.0"}])
		with self.assertRaisesRegex(ValueError, "unavailable"):
			get_profile("frappe-v15")


class CLITests(unittest.TestCase):
	def test_clean_checkout_indexes_and_dirty_checkout_is_rejected(self):
		with tempfile.TemporaryDirectory() as directory:
			base = Path(directory)
			repo = base / "repo"
			repo.mkdir()
			subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
			(repo / "code.py").write_text("def hello():\n    return 1\n")
			subprocess.run(["git", "add", "code.py"], cwd=repo, check=True)
			subprocess.run(
				[
					"git",
					"-c",
					"user.name=Test",
					"-c",
					"user.email=test@example.invalid",
					"commit",
					"-qm",
					"test",
				],
				cwd=repo,
				check=True,
			)
			revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
			manifest = base / "manifest.json"
			manifest.write_text(
				json.dumps(
					{
						"project_id": "project",
						"sources": [
							{
								"app": "example",
								"repository": "example/app",
								"revision": revision,
								"version": "16",
								"root": "repo",
							}
						],
					}
				)
			)
			with contextlib.redirect_stdout(io.StringIO()):
				main(["index", str(manifest), "--output", str(base / "out.json")])
			self.assertTrue(json.loads((base / "out.json").read_text())["coverage"]["checkout_verified"])
			(repo / "code.py").write_text("def hello():\n    return 2\n")
			with self.assertRaisesRegex(ValueError, "clean checkout"):
				main(["index", str(manifest), "--output", str(base / "out2.json")])

	def test_subdirectory_cannot_impersonate_repository_root(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			subprocess.run(["git", "init", "-q"], cwd=root, check=True)
			(root / "subdir").mkdir()
			manifest = root / "manifest.json"
			manifest.write_text(
				json.dumps(
					{
						"project_id": "project",
						"sources": [
							{
								"app": "example",
								"repository": "example/app",
								"revision": "a" * 40,
								"version": "16",
								"root": "subdir",
							}
						],
					}
				)
			)
			with self.assertRaisesRegex(ValueError, "repository root"):
				main(["index", str(manifest), "--output", str(root / "out.json")])


if __name__ == "__main__":
	unittest.main()
