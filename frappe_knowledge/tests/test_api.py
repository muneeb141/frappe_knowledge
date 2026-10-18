"""Site-level checks for the starter's restricted snapshot workflow."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.classes import IntegrationTestCase

from frappe_knowledge.api import MAX_IMPORT_BYTES, get_context, import_snapshot
from frappe_knowledge.core.index import SourceRoot, _canonical, _digest, build_snapshot, retrieve_context
from frappe_knowledge.ingest import request_local_index, run_local_index
from frappe_knowledge.site_overlay import capture_site_overlay, get_site_overlay
from frappe_knowledge.storage import load_snapshot

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


class TestKnowledgeAPI(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.project = f"fk-test-{frappe.generate_hash(length=10)}"
		frappe.get_doc(
			{
				"doctype": "FK Project",
				"project_key": self.project,
				"project_title": "Knowledge integration test",
				"framework_major": "16",
			}
		).insert()
		manifest = json.loads((FIXTURES / "manifest-v16.json").read_text())
		sources = [
			SourceRoot(
				item["app"],
				item["repository"],
				item["revision"],
				FIXTURES / item["root"],
				item["version"],
			)
			for item in manifest["sources"]
		]
		self.snapshot = build_snapshot(self.project, sources)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_import_retrieve_and_duplicate_are_scoped(self):
		name = import_snapshot(self.project, self.snapshot)
		self.assertEqual(import_snapshot(self.project, self.snapshot), name)
		context = get_context(name, "Payroll Entry")
		self.assertEqual(context["project_id"], self.project)
		self.assertEqual(context["profile_id"], "frappe-v16")
		self.assertEqual(context["snapshot_id"], name)
		self.assertEqual(frappe.db.get_value("FK Snapshot", name, "knowledge_profile"), "frappe-v16")
		stored = frappe.get_doc("FK Snapshot", name)
		self.assertEqual(stored.storage_format, "Indexed Rows")
		self.assertFalse(stored.graph_json)
		self.assertGreater(stored.stored_rows, len(self.snapshot["nodes"]) + len(self.snapshot["edges"]))
		self.assertEqual(load_snapshot(stored), self.snapshot)
		self.assertEqual(context, retrieve_context(self.snapshot, self.project, "Payroll Entry"))
		self.assertTrue(any(node["title"] == "Journal Entry" for node in context["nodes"]))
		self.assertIn("CONTROLLER_MODULE_FOR", context["relation_meanings"])
		self.assertEqual(frappe.db.count("FK Snapshot", {"project": self.project}), 1)
		other_project = f"fk-test-{frappe.generate_hash(length=10)}"
		frappe.get_doc(
			{
				"doctype": "FK Project",
				"project_key": other_project,
				"project_title": "Other knowledge project",
				"framework_major": "16",
			}
		).insert()
		with self.assertRaises(frappe.ValidationError):
			import_snapshot(other_project, self.snapshot)

	def test_snapshot_cannot_be_edited_or_deleted(self):
		name = import_snapshot(self.project, self.snapshot)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc("FK Snapshot", name).save()
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("FK Snapshot", name)
		self.assertTrue(frappe.db.exists("FK Snapshot", name))

	def test_bad_payload_and_guest_access_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			import_snapshot(self.project, "not JSON")
		with self.assertRaises(frappe.ValidationError):
			import_snapshot(self.project, "x" * (MAX_IMPORT_BYTES + 1))
		name = import_snapshot(self.project, self.snapshot)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			get_context(name, "Payroll Entry")
		with self.assertRaises(frappe.PermissionError):
			import_snapshot(self.project, self.snapshot)

	def test_revision_version_and_context_budget_are_checked(self):
		bad_revision = deepcopy(self.snapshot)
		bad_revision["sources"][0]["revision"] = "0" * 40
		bad_revision["snapshot_id"] = _digest(
			_canonical({key: value for key, value in bad_revision.items() if key != "snapshot_id"})
		)
		with self.assertRaises(frappe.ValidationError):
			import_snapshot(self.project, bad_revision)

		bad_major = deepcopy(self.snapshot)
		bad_major["sources"][0]["version"] = "15"
		bad_major["snapshot_id"] = _digest(
			_canonical({key: value for key, value in bad_major.items() if key != "snapshot_id"})
		)
		with self.assertRaises(frappe.ValidationError):
			import_snapshot(self.project, bad_major)

		name = import_snapshot(self.project, self.snapshot)
		with self.assertRaises(frappe.ValidationError):
			get_context(name, "Payroll Entry", "not-a-number")
		with self.assertRaises(frappe.ValidationError):
			get_context(name, "Payroll Entry", 100)

	def test_project_profile_cannot_be_changed_after_creation(self):
		project = frappe.get_doc("FK Project", self.project)
		project.knowledge_profile = "frappe-v15"
		with self.assertRaises(frappe.ValidationError):
			project.save()

	def test_local_index_worker_stores_a_verified_checkout_snapshot(self):
		manifest = json.loads((FIXTURES / "manifest-v16.json").read_text())
		sources = [
			SourceRoot(
				item["app"], item["repository"], item["revision"], FIXTURES / item["root"], item["version"]
			)
			for item in manifest["sources"]
		]
		with patch("frappe_knowledge.ingest.installed_source_roots", return_value=sources):
			name = run_local_index(self.project)
		stored = frappe.get_doc("FK Snapshot", name)
		metadata = json.loads(stored.metadata_json)
		self.assertEqual(stored.storage_format, "Indexed Rows")
		self.assertGreater(stored.source_chunks, 0)
		self.assertEqual(frappe.db.count("FK Source Chunk", {"snapshot": name}), stored.source_chunks)
		self.assertTrue(metadata["coverage"]["checkout_verified"])
		self.assertEqual(metadata["coverage"]["source_mode"], "installed_local_checkout")
		self.assertEqual(load_snapshot(stored)["snapshot_id"], name)
		self.assertTrue(get_context(name, "Payroll Entry")["nodes"])
		symbol_context = get_context(name, "get_advance_deductions")
		self.assertEqual(symbol_context["nodes"][0]["title"], "get_advance_deductions")
		self.assertTrue(symbol_context["source_matches"])
		self.assertIn("get_advance_deductions", symbol_context["source_matches"][0]["content"])
		self.assertLessEqual(symbol_context["characters"], 16000)
		bounded = get_context(name, "get_advance_deductions", 4000)
		self.assertLessEqual(bounded["characters"], 4000)
		self.assertTrue(bounded["source_matches"])
		self.assertIn("get_advance_deductions", bounded["source_matches"][0]["content"])
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			get_context(name, "get_advance_deductions")
		frappe.set_user("Administrator")

	def test_local_index_request_is_admin_only_and_queues_no_path(self):
		with patch("frappe_knowledge.ingest.frappe.enqueue") as enqueue:
			result = request_local_index(self.project)
		self.assertEqual(result["status"], "queued_or_running")
		self.assertEqual(enqueue.call_args.kwargs["project"], self.project)
		self.assertNotIn("path", enqueue.call_args.kwargs)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			request_local_index(self.project)

	def test_site_overlay_is_scoped_immutable_and_omits_record_values(self):
		snapshot = import_snapshot(self.project, self.snapshot)
		overlay = capture_site_overlay(self.project, snapshot)
		self.assertEqual(capture_site_overlay(self.project, snapshot), overlay)
		data = get_site_overlay(overlay)
		self.assertEqual(data["source_snapshot"], snapshot)
		self.assertEqual(data["project_id"], self.project)
		self.assertEqual(data["site"], frappe.local.site)
		self.assertEqual(data["source_identity"], "not_verified_by_overlay")
		context = get_context(snapshot, "Payroll Entry", site_overlay=overlay)
		self.assertEqual(context["site_overlay"]["overlay_id"], overlay)
		self.assertLessEqual(context["characters"], 16000)
		for field in data["fields"]:
			self.assertNotIn("default", field)
			self.assertNotIn("value", field)
			self.assertNotIn("depends_on", field)
		stored = frappe.get_doc("FK Site Overlay", overlay)
		self.assertEqual(stored.field_count, len(data["fields"]))
		with self.assertRaises(frappe.ValidationError):
			stored.save()
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("FK Site Overlay", overlay)
		other = frappe.get_doc(
			{
				"doctype": "FK Project",
				"project_key": f"fk-other-{frappe.generate_hash(length=10)}",
				"project_title": "Other overlay project",
				"framework_major": "16",
			}
		).insert()
		with self.assertRaises(frappe.ValidationError):
			capture_site_overlay(other.name, snapshot)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			get_site_overlay(overlay)
		with self.assertRaises(frappe.PermissionError):
			capture_site_overlay(self.project, snapshot)
