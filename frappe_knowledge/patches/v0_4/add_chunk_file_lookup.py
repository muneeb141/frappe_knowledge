"""Find source text surrounding an exact node's cited line."""

import frappe


def execute():
	frappe.db.add_index("FK Source Chunk", ["snapshot", "file_sha256", "start_line"], "fk_chunk_file_line")
