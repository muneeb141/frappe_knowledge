"""Frappe adapter. Knowledge access is checked before source context is read."""

import json

import frappe

from frappe_knowledge.core.index import retrieve_context, validate_snapshot
from frappe_knowledge.core.profiles import validate_sources
from frappe_knowledge.site_overlay import attach_site_overlay, get_site_overlay
from frappe_knowledge.source_index import attach_source_matches
from frappe_knowledge.storage import load_snapshot, metadata_for, retrieve_indexed, write_rows

MAX_IMPORT_BYTES = 20_000_000


@frappe.whitelist(methods=["POST"])
def import_snapshot(project, payload):
	frappe.only_for("System Manager")
	project_doc = frappe.get_doc("FK Project", project)
	project_doc.check_permission("write")
	if isinstance(payload, str):
		raw = payload
	elif isinstance(payload, dict):
		raw = json.dumps(payload)
	else:
		frappe.throw("Snapshot payload must be a JSON object")
	if len(raw.encode("utf-8")) > MAX_IMPORT_BYTES:
		frappe.throw("Snapshot exceeds the 20 MB import limit")
	try:
		parsed = json.loads(raw)
		if not isinstance(parsed, dict):
			raise ValueError("Snapshot payload must be a JSON object")
		snapshot = validate_snapshot(parsed, project, profile_id=project_doc.knowledge_profile)
		validate_sources(project_doc.knowledge_profile, snapshot["sources"])
	except (ValueError, KeyError, TypeError, IndexError):
		frappe.throw("Invalid snapshot payload")
	return _store_snapshot(project_doc, snapshot, verify_roundtrip=True)


def _store_snapshot(project_doc, snapshot, *, verify_roundtrip):
	"""Persist a validated snapshot in the current transaction.

	A local worker can skip full graph reconstruction after a row-count check;
	the bounded HTTP path still performs exact round-trip verification.
	"""
	project = project_doc.name
	if frappe.db.exists("FK Snapshot", snapshot["snapshot_id"]):
		existing = frappe.get_doc("FK Snapshot", snapshot["snapshot_id"])
		existing.check_permission("read")
		if existing.project != project or existing.knowledge_profile != project_doc.knowledge_profile:
			frappe.throw("Snapshot is already bound to another project or profile")
		return existing.name
	doc = frappe.get_doc(
		{
			"doctype": "FK Snapshot",
			"project": project,
			"knowledge_profile": project_doc.knowledge_profile,
			"snapshot_id": snapshot["snapshot_id"],
			"storage_format": "Indexed Rows",
			"metadata_json": json.dumps(metadata_for(snapshot), ensure_ascii=False),
			"indexed_files": len(snapshot["files"]),
			"node_count": len(snapshot["nodes"]),
			"edge_count": len(snapshot["edges"]),
			"coverage": "Partial",
		}
	)
	# Both callers authorize the project before reaching this internal writer.
	doc.insert(ignore_permissions=True)
	row_count = write_rows(snapshot)
	if verify_roundtrip:
		load_snapshot(doc)
	frappe.db.set_value("FK Snapshot", doc.name, "stored_rows", row_count, update_modified=False)
	return doc.name


@frappe.whitelist()
def get_context(snapshot, query, max_chars=16000, site_overlay=None):
	frappe.only_for("System Manager")
	doc = frappe.get_doc("FK Snapshot", snapshot)
	doc.check_permission("read")
	project = frappe.get_doc("FK Project", doc.project)
	project.check_permission("read")
	if doc.knowledge_profile != project.knowledge_profile:
		frappe.throw("Snapshot profile does not match its project")
	overlay_data = get_site_overlay(site_overlay) if site_overlay else None
	if overlay_data and (
		overlay_data["project_id"] != project.name
		or overlay_data["source_snapshot"] != doc.name
		or overlay_data["profile_id"] != project.knowledge_profile
	):
		frappe.throw("Site overlay does not match the selected source snapshot")
	try:
		budget = int(max_chars)
		if overlay_data and budget < 4000:
			raise ValueError("Site overlay needs a larger context budget")
		if doc.storage_format == "Indexed Rows":
			metadata = json.loads(doc.metadata_json)
			validate_sources(project.knowledge_profile, metadata["sources"])
			if doc.source_chunks and budget >= 4000:
				natural_question = len(query.split()) >= 3
				graph_budget = (
					(budget if budget >= 6000 else 2000)
					if budget < 8000
					else max(2000, int(budget * (0.5 if natural_question else 0.6)))
				)
				if overlay_data:
					graph_budget = min(graph_budget, max(2000, budget - 1200))
				context = retrieve_indexed(
					doc,
					query,
					max_nodes=5 if natural_question else 20,
					max_chars=graph_budget,
				)
				if overlay_data:
					context = attach_site_overlay(context, overlay_data, query, budget - 256)
				return attach_source_matches(doc, context, query, budget)
			context = retrieve_indexed(doc, query, max_chars=budget - 1000 if overlay_data else budget)
			return attach_site_overlay(context, overlay_data, query, budget) if overlay_data else context
		graph = json.loads(doc.graph_json)
		validate_sources(project.knowledge_profile, graph["sources"])
		context = retrieve_context(
			graph,
			project.name,
			query,
			profile_id=project.knowledge_profile,
			max_chars=budget - 1000 if overlay_data else budget,
		)
		return attach_site_overlay(context, overlay_data, query, budget) if overlay_data else context
	except (ValueError, TypeError, KeyError):
		frappe.throw("Invalid context request")
