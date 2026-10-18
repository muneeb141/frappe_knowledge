import json

import frappe
from frappe.model.document import Document

from frappe_knowledge.core.index import snapshot_profile, validate_snapshot
from frappe_knowledge.core.profiles import validate_sources


class FKSnapshot(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw("Snapshots are immutable; import a new snapshot")
		project = frappe.get_doc("FK Project", self.project)
		if self.knowledge_profile != project.knowledge_profile:
			frappe.throw("Snapshot profile does not match its project")
		if self.storage_format == "Indexed Rows":
			if self.graph_json or not self.metadata_json:
				frappe.throw("Indexed snapshots require separate metadata and rows")
			data = json.loads(self.metadata_json)
			if (
				data.get("project_id") != self.project
				or data.get("snapshot_id") != self.snapshot_id
				or snapshot_profile(data) != self.knowledge_profile
			):
				frappe.throw("Snapshot metadata does not match its project or profile")
		else:
			data = validate_snapshot(
				json.loads(self.graph_json), self.project, profile_id=self.knowledge_profile
			)
			if data["snapshot_id"] != self.snapshot_id:
				frappe.throw("Snapshot identifier mismatch")
		try:
			validate_sources(self.knowledge_profile, data["sources"])
		except ValueError as exc:
			frappe.throw(str(exc))

	def before_rename(self, old, new, merge=False):
		frappe.throw("Snapshot identifiers are immutable")

	def on_trash(self):
		frappe.throw("Snapshots are immutable; import a new snapshot")
