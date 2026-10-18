"""Internal indexed snapshot row; access only through an authorized snapshot."""

import frappe
from frappe.model.document import Document


class FKKnowledgeRow(Document):
	def validate(self):
		frappe.throw("Knowledge rows are immutable and managed by snapshot import")

	def on_trash(self):
		frappe.throw("Knowledge rows are immutable")

	def before_rename(self, old, new, merge=False):
		frappe.throw("Knowledge rows are immutable")
