"""Copy historical JSON snapshots into indexed rows, retaining JSON for rollback."""

import json

import frappe

from frappe_knowledge.core.index import validate_snapshot
from frappe_knowledge.storage import load_snapshot, metadata_for, write_rows


def execute():
	frappe.db.add_index("FK Knowledge Row", ["snapshot", "row_kind", "lookup_key"], "fk_row_lookup")
	frappe.db.add_index("FK Knowledge Row", ["snapshot", "row_kind", "source_key"], "fk_row_source")
	frappe.db.add_index("FK Knowledge Row", ["snapshot", "row_kind", "target_key"], "fk_row_target")
	for row in frappe.get_all(
		"FK Snapshot", fields=["name", "project", "knowledge_profile", "graph_json", "storage_format"]
	):
		if row.storage_format == "Indexed Rows" or not row.graph_json:
			continue
		snapshot = validate_snapshot(
			json.loads(row.graph_json), row.project, profile_id=row.knowledge_profile
		)
		count = write_rows(snapshot)
		doc = frappe._dict(
			name=row.name,
			project=row.project,
			knowledge_profile=row.knowledge_profile,
			metadata_json=json.dumps(metadata_for(snapshot), ensure_ascii=False),
		)
		load_snapshot(doc)
		frappe.db.set_value(
			"FK Snapshot",
			row.name,
			{
				"storage_format": "Indexed Rows",
				"metadata_json": doc.metadata_json,
				"stored_rows": count,
			},
			update_modified=False,
		)
