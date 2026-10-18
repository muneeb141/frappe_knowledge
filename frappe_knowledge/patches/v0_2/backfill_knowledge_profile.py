"""Bind existing schema-1 projects and snapshots to their sole historical profile."""

import frappe


def execute():
	for doctype in ("FK Project", "FK Snapshot"):
		frappe.db.sql(
			f"UPDATE `tab{doctype}` SET knowledge_profile = %s "
			"WHERE knowledge_profile IS NULL OR knowledge_profile = ''",
			("frappe-v16",),
		)
