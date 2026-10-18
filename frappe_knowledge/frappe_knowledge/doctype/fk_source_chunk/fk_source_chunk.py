"""Internal, immutable source text projection; read only after snapshot authorization."""

import frappe
from frappe.model.document import Document


class FKSourceChunk(Document):
	def validate(self):
		frappe.throw("Source chunks are immutable and managed by local indexing")

	def on_trash(self):
		frappe.throw("Source chunks are immutable")

	def before_rename(self, old, new, merge=False):
		frappe.throw("Source chunks are immutable")
