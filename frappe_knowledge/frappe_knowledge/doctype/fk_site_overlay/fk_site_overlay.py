"""Immutable, site-bound metadata captures kept separate from source snapshots."""

import json

import frappe
from frappe.model.document import Document

from frappe_knowledge.core.index import _canonical, _digest


class FKSiteOverlay(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw("Site overlays are immutable; capture another overlay")
		project = frappe.get_doc("FK Project", self.project)
		snapshot = frappe.get_doc("FK Snapshot", self.source_snapshot)
		if snapshot.project != project.name or self.knowledge_profile != project.knowledge_profile:
			frappe.throw("Site overlay does not match its project and source snapshot")
		data = json.loads(self.metadata_json)
		if (
			data.get("project_id") != project.name
			or data.get("source_snapshot") != snapshot.name
			or data.get("profile_id") != project.knowledge_profile
			or data.get("site") != frappe.local.site
			or self.site != data["site"]
			or self.field_count != len(data.get("fields", []))
			or self.overlay_id != _digest(_canonical(data))
		):
			frappe.throw("Site overlay identity does not match its metadata")

	def before_rename(self, old, new, merge=False):
		frappe.throw("Site overlay identifiers are immutable")

	def on_trash(self):
		frappe.throw("Site overlays are immutable")
