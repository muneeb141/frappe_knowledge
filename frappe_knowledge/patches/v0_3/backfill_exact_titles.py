"""Add a rebuildable exact-title projection to already indexed snapshots."""

import json

import frappe

from frappe_knowledge.storage import ROW_FIELDS, _row, title_key


def execute():
	for snapshot in frappe.get_all("FK Snapshot", filters={"storage_format": "Indexed Rows"}, pluck="name"):
		cursor = ""
		while True:
			nodes = frappe.db.sql(
				"SELECT name, lookup_key, payload_json FROM `tabFK Knowledge Row` "
				"WHERE snapshot = %s AND row_kind = 'Node' AND name > %s ORDER BY name LIMIT 500",
				(snapshot, cursor),
				as_dict=True,
			)
			if not nodes:
				break
			rows = []
			for node in nodes:
				payload = json.loads(node.payload_json)
				if payload["resolved"]:
					rows.append(
						_row(snapshot, "Exact", title_key(payload["title"]), source_key=node.lookup_key)
					)
			if rows:
				frappe.db.bulk_insert(
					"FK Knowledge Row", ROW_FIELDS, rows, ignore_duplicates=True, chunk_size=500
				)
			cursor = nodes[-1].name
		frappe.db.set_value(
			"FK Snapshot",
			snapshot,
			"stored_rows",
			frappe.db.count("FK Knowledge Row", {"snapshot": snapshot}),
			update_modified=False,
		)
