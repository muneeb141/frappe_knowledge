"""Add scoped lookup and InnoDB full-text search for derived source chunks."""

import frappe


def execute():
	frappe.db.add_index("FK Source Chunk", ["snapshot"], "fk_chunk_snapshot")
	if frappe.db.db_type == "mariadb":
		indexes = frappe.db.sql("SHOW INDEX FROM `tabFK Source Chunk` WHERE Key_name = 'fk_source_text'")
		if not indexes:
			frappe.db.sql("CREATE FULLTEXT INDEX `fk_source_text` ON `tabFK Source Chunk` (`search_text`)")
