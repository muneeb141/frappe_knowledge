"""Permission-scoped captures of effective site field metadata."""

import json
from collections import defaultdict

import frappe

from frappe_knowledge.core.index import _canonical, _digest, normalized_title

MAX_CUSTOMIZATION_RECORDS = 1000
MAX_OVERLAY_BYTES = 1_000_000
LINK_FIELDS = {"Link", "Table", "Table MultiSelect", "Dynamic Link"}


def _visible_customizations(doctype, fields):
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(f"Cannot read {doctype} site metadata", frappe.PermissionError)
	rows = frappe.get_list(doctype, fields=fields, order_by="name asc", limit=MAX_CUSTOMIZATION_RECORDS + 1)
	if len(rows) > MAX_CUSTOMIZATION_RECORDS:
		frappe.throw(f"Too many {doctype} records for a bounded site overlay")
	return rows


def _effective_field_rows():
	custom_fields = _visible_customizations("Custom Field", ["name", "dt", "fieldname"])
	setters = _visible_customizations(
		"Property Setter", ["name", "doc_type", "doctype_or_field", "field_name"]
	)
	origins = defaultdict(lambda: {"custom_fields": [], "property_setters": []})
	for row in custom_fields:
		if row.dt and row.fieldname:
			origins[(row.dt, row.fieldname)]["custom_fields"].append(row.name)
	excluded_setters = 0
	for row in setters:
		if row.doctype_or_field == "DocField" and row.doc_type and row.field_name:
			origins[(row.doc_type, row.field_name)]["property_setters"].append(row.name)
		else:
			excluded_setters += 1

	fields = []
	unresolved = []
	for (doctype, fieldname), references in sorted(origins.items()):
		try:
			field = frappe.get_meta(doctype).get_field(fieldname)
		except frappe.DoesNotExistError:
			field = None
		if field is None:
			unresolved.append({"doctype": doctype, "fieldname": fieldname})
			continue
		fields.append(
			{
				"doctype": doctype,
				"fieldname": fieldname,
				"label": field.label,
				"fieldtype": field.fieldtype,
				"options": field.options if field.fieldtype in LINK_FIELDS else None,
				"required": int(bool(field.reqd)),
				"hidden": int(bool(field.hidden)),
				"read_only": int(bool(field.read_only)),
				"permlevel": int(field.permlevel or 0),
				"custom_fields": sorted(references["custom_fields"]),
				"property_setters": sorted(references["property_setters"]),
			}
		)
	return fields, {
		"custom_fields_seen": len(custom_fields),
		"field_property_setters_seen": len(setters) - excluded_setters,
		"other_property_setters_excluded": excluded_setters,
		"unresolved_fields": unresolved,
		"excluded": [
			"field defaults",
			"conditional scripts",
			"workflow rules",
			"custom permissions",
			"record values",
		],
	}


@frappe.whitelist(methods=["POST"])
def capture_site_overlay(project, source_snapshot):
	"""Capture metadata on this site only, after authorizing the project and snapshot."""
	frappe.only_for("System Manager")
	project_doc = frappe.get_doc("FK Project", project)
	project_doc.check_permission("write")
	snapshot_doc = frappe.get_doc("FK Snapshot", source_snapshot)
	snapshot_doc.check_permission("read")
	if (
		snapshot_doc.project != project_doc.name
		or snapshot_doc.knowledge_profile != project_doc.knowledge_profile
	):
		frappe.throw("Source snapshot does not match the project")

	fields, coverage = _effective_field_rows()
	data = {
		"schema_version": 1,
		"project_id": project_doc.name,
		"source_snapshot": snapshot_doc.name,
		"profile_id": project_doc.knowledge_profile,
		"site": frappe.local.site,
		"source_identity": "not_verified_by_overlay",
		"coverage": coverage,
		"fields": fields,
	}
	raw = _canonical(data)
	if len(raw.encode("utf-8")) > MAX_OVERLAY_BYTES:
		frappe.throw("Site overlay exceeds the 1 MB limit")
	overlay_id = _digest(raw)
	if frappe.db.exists("FK Site Overlay", overlay_id):
		existing = frappe.get_doc("FK Site Overlay", overlay_id)
		existing.check_permission("read")
		return existing.name
	doc = frappe.get_doc(
		{
			"doctype": "FK Site Overlay",
			"project": project_doc.name,
			"source_snapshot": snapshot_doc.name,
			"overlay_id": overlay_id,
			"site": frappe.local.site,
			"knowledge_profile": project_doc.knowledge_profile,
			"field_count": len(fields),
			"metadata_json": raw,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def get_site_overlay(overlay):
	"""Return only the metadata of an authorized overlay from this site."""
	frappe.only_for("System Manager")
	doc = frappe.get_doc("FK Site Overlay", overlay)
	doc.check_permission("read")
	frappe.get_doc("FK Project", doc.project).check_permission("read")
	frappe.get_doc("FK Snapshot", doc.source_snapshot).check_permission("read")
	if doc.site != frappe.local.site:
		frappe.throw("Site overlay belongs to another site", frappe.PermissionError)
	return {"overlay_id": doc.name, **json.loads(doc.metadata_json)}


def attach_site_overlay(context, overlay_data, query, max_chars):
	"""Add bounded, relevant site facts without changing source evidence."""

	def recount():
		for _ in range(4):
			size = len(_canonical(context))
			if context.get("characters") == size:
				break
			context["characters"] = size

	doctype_names = {
		normalized_title(node["title"]) for node in context.get("nodes", []) if node.get("kind") == "doctype"
	}
	question = normalized_title(query)
	matching = [
		field
		for field in overlay_data["fields"]
		if normalized_title(field["doctype"]) in doctype_names
		or normalized_title(field["doctype"]) in question
	]
	coverage = overlay_data["coverage"]
	context["site_overlay"] = {
		"overlay_id": overlay_data["overlay_id"],
		"site": overlay_data["site"],
		"source_snapshot": overlay_data["source_snapshot"],
		"source_identity": overlay_data["source_identity"],
		"effective_field_count": len(overlay_data["fields"]),
		"excluded": coverage["excluded"],
		"matching_fields": matching[:12],
		"matching_fields_truncated": len(matching) > 12,
	}
	context["truncated"] |= context["site_overlay"]["matching_fields_truncated"]
	recount()
	while context["characters"] > max_chars and context["site_overlay"]["matching_fields"]:
		context["site_overlay"]["matching_fields"].pop()
		context["site_overlay"]["matching_fields_truncated"] = True
		context["truncated"] = True
		recount()
	if context["characters"] > max_chars:
		frappe.throw("Context budget is too small for the site overlay")
	return context
