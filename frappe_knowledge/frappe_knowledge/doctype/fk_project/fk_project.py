import frappe
from frappe.model.document import Document

from frappe_knowledge.core.profiles import get_profile


class FKProject(Document):
	def validate(self):
		try:
			profile = get_profile(self.knowledge_profile)
		except ValueError:
			frappe.throw("Knowledge profile is unavailable")
		if self.framework_major != profile.framework_major:
			frappe.throw("Framework major does not match the knowledge profile")
		if not self.is_new():
			previous = self.get_doc_before_save()
			if previous and self.knowledge_profile != previous.knowledge_profile:
				frappe.throw("Create another project to change knowledge profile")
