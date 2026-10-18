"""Frappe storage adapter for immutable, indexed snapshot rows.

Callers must authorize the snapshot and project before reading these rows.
"""

import heapq
import json
import re

import frappe

from frappe_knowledge.core.index import (
	_canonical,
	_digest,
	normalized_title,
	pack_context,
	snapshot_profile,
	validate_snapshot,
	walk_priority,
)

ROW_FIELDS = [
	"name",
	"snapshot",
	"row_kind",
	"lookup_key",
	"source_key",
	"target_key",
	"position",
	"payload_json",
]
MAX_TERM_CANDIDATES = 500


def node_key(node_id):
	return _digest(node_id)


def title_key(title):
	"""Normalize spaces, underscores and punctuation for exact name lookup."""
	return _digest(normalized_title(title))


def metadata_for(snapshot):
	return {key: value for key, value in snapshot.items() if key not in {"files", "nodes", "edges"}}


def _row(snapshot_id, kind, key, payload=None, source_key=None, target_key=None, position=None):
	name = _digest(":.=".join((snapshot_id, kind, key, source_key or "", target_key or "")))
	return (
		name,
		snapshot_id,
		kind,
		key,
		source_key,
		target_key,
		position,
		_canonical(payload) if payload is not None else None,
	)


def _snapshot_rows(snapshot):
	snapshot_id = snapshot["snapshot_id"]
	for path, digest in snapshot["files"].items():
		yield _row(snapshot_id, "File", _digest(path), {"path": path, "sha256": digest})
	for node in snapshot["nodes"]:
		key = node_key(node["id"])
		yield _row(snapshot_id, "Node", key, node)
		if node["resolved"]:
			yield _row(snapshot_id, "Exact", title_key(node["title"]), source_key=key)
		for term in sorted(set(re.findall(r"[a-z0-9]+", node["title"].lower()))):
			if node["resolved"]:
				yield _row(snapshot_id, "Term", _digest(term), source_key=key)
	for position, edge in enumerate(snapshot["edges"]):
		yield _row(
			snapshot_id,
			"Edge",
			_digest(_canonical(edge)),
			edge,
			node_key(edge["source"]),
			node_key(edge["target"]),
			position,
		)


def write_rows(snapshot):
	"""Write rows in bounded batches within the caller's transaction."""
	expected = 0

	def counted_rows():
		nonlocal expected
		for row in _snapshot_rows(snapshot):
			expected += 1
			yield row

	frappe.db.bulk_insert(
		"FK Knowledge Row", ROW_FIELDS, counted_rows(), ignore_duplicates=True, chunk_size=500
	)
	actual = frappe.db.count("FK Knowledge Row", {"snapshot": snapshot["snapshot_id"]})
	if actual != expected:
		raise ValueError("Indexed row count does not match the snapshot")
	return actual


def load_snapshot(snapshot_doc):
	"""Reconstruct a complete snapshot for migration checks and offline exports."""
	result = json.loads(snapshot_doc.metadata_json)
	result.update({"files": {}, "nodes": [], "edges": []})
	rows = frappe.db.sql(
		"SELECT row_kind, position, payload_json FROM `tabFK Knowledge Row` WHERE snapshot = %s AND row_kind IN ('File', 'Node', 'Edge')",
		(snapshot_doc.name,),
		as_dict=True,
	)
	positioned_edges = []
	for row in rows:
		payload = json.loads(row.payload_json)
		if row.row_kind == "File":
			result["files"][payload["path"]] = payload["sha256"]
		elif row.row_kind == "Node":
			result["nodes"].append(payload)
		elif row.row_kind == "Edge":
			positioned_edges.append((row.position, payload))
	result["files"] = dict(sorted(result["files"].items()))
	result["nodes"].sort(key=lambda node: node["id"])
	result["edges"] = [edge for _, edge in sorted(positioned_edges, key=lambda item: item[0])]
	return validate_snapshot(result, snapshot_doc.project, profile_id=snapshot_doc.knowledge_profile)


def _fetch_nodes(snapshot_id, keys):
	if not keys:
		return {}
	placeholders = ",".join(["%s"] * len(keys))
	rows = frappe.db.sql(
		f"SELECT lookup_key, payload_json FROM `tabFK Knowledge Row` WHERE snapshot = %s AND row_kind = 'Node' AND lookup_key IN ({placeholders})",
		(snapshot_id, *keys),
		as_dict=True,
	)
	return {row.lookup_key: json.loads(row.payload_json) for row in rows}


def _fetch_edges(snapshot_id, keys, limit=10001):
	if not keys:
		return [], False
	placeholders = ",".join(["%s"] * len(keys))
	rows = frappe.db.sql(
		f"SELECT lookup_key, source_key, target_key, position, payload_json FROM `tabFK Knowledge Row` "
		f"WHERE snapshot = %s AND row_kind = 'Edge' AND (source_key IN ({placeholders}) OR target_key IN ({placeholders})) "
		"ORDER BY position LIMIT %s",
		(snapshot_id, *keys, *keys, limit),
		as_dict=True,
	)
	return rows[: limit - 1], len(rows) == limit


def retrieve_indexed(snapshot_doc, query, *, max_nodes=20, max_chars=16000, max_hops=2):
	"""Search terms and expand indexed edges without loading the entire graph."""
	if not isinstance(query, str) or not query.strip() or len(query) > 500:
		raise ValueError("Query must contain 1-500 characters")
	if not 1 <= max_nodes <= 50 or not 2000 <= max_chars <= 64000 or not 0 <= max_hops <= 3:
		raise ValueError("Context budget is out of range")
	metadata = json.loads(snapshot_doc.metadata_json)
	if (
		metadata.get("snapshot_id") != snapshot_doc.name
		or metadata.get("project_id") != snapshot_doc.project
		or snapshot_profile(metadata) != snapshot_doc.knowledge_profile
	):
		raise ValueError("Snapshot metadata mismatch")
	terms = sorted(set(re.findall(r"[a-z0-9]+", query.lower())))
	matches, seed_truncated = [], False
	exact_rows = frappe.db.sql(
		"SELECT source_key FROM `tabFK Knowledge Row` WHERE snapshot = %s AND row_kind = 'Exact' AND lookup_key = %s",
		(snapshot_doc.name, title_key(query)),
		as_dict=True,
	)
	exact_keys = {row.source_key for row in exact_rows}
	if terms:
		term_keys = [_digest(term) for term in terms]
		placeholders = ",".join(["%s"] * len(term_keys))
		rows = frappe.db.sql(
			f"SELECT source_key, COUNT(DISTINCT lookup_key) AS term_hits FROM `tabFK Knowledge Row` "
			f"WHERE snapshot = %s AND row_kind = 'Term' AND lookup_key IN ({placeholders}) "
			f"GROUP BY source_key ORDER BY term_hits DESC, source_key LIMIT %s",
			(snapshot_doc.name, *term_keys, MAX_TERM_CANDIDATES + 1),
			as_dict=True,
		)
		seed_truncated = len(rows) > MAX_TERM_CANDIDATES
		matches = [row.source_key for row in rows[:MAX_TERM_CANDIDATES]]
	matches = list(dict.fromkeys([*exact_keys, *matches]))
	cache = _fetch_nodes(snapshot_doc.name, matches)
	query_terms = set(terms)

	def score(node):
		words = set(re.findall(r"[a-z0-9]+", node["title"].lower()))
		return len(query_terms & words) * (5 if node["kind"] == "doctype" else 1)

	ranked = sorted(
		(
			node
			for node in cache.values()
			if node["resolved"] and (score(node) or node_key(node["id"]) in exact_keys)
		),
		key=lambda node: (node_key(node["id"]) not in exact_keys, -score(node), node["id"]),
	)
	exact = [node for node in ranked if node_key(node["id"]) in exact_keys]
	normalized_query = normalized_title(query)
	mentioned = sorted(
		(
			node
			for node in ranked
			if node["kind"] == "doctype"
			and len(normalized_title(node["title"])) >= 8
			and normalized_title(node["title"]) in normalized_query
		),
		key=lambda node: (-len(normalized_title(node["title"])), node["id"]),
	)
	queue = [(0, 0, node["id"], node_key(node["id"])) for node in (exact or mentioned[:3] or ranked[:3])]
	heapq.heapify(queue)
	selected_keys, seen = [], set()
	truncated = seed_truncated
	while queue and len(selected_keys) < max_nodes:
		cost, depth, _, key = heapq.heappop(queue)
		if key in seen:
			continue
		seen.add(key)
		if key not in cache:
			cache.update(_fetch_nodes(snapshot_doc.name, [key]))
		if key not in cache:
			continue
		selected_keys.append(key)
		if depth < max_hops:
			adjacent, overflow = _fetch_edges(snapshot_doc.name, [key])
			truncated |= overflow
			neighbors = {neighbor for edge in adjacent for neighbor in (edge.source_key, edge.target_key)}
			cache.update(
				_fetch_nodes(snapshot_doc.name, [neighbor for neighbor in neighbors if neighbor not in cache])
			)
			for edge in adjacent:
				if edge.source_key == key:
					neighbor, reverse = edge.target_key, False
				else:
					neighbor, reverse = edge.source_key, True
				if neighbor != key:
					relation = json.loads(edge.payload_json)["relation"]
					heapq.heappush(
						queue,
						(
							cost + walk_priority(relation, reverse=reverse),
							depth + 1,
							cache[neighbor]["id"],
							neighbor,
						),
					)
	truncated |= bool(queue)
	selected = [cache[key] for key in selected_keys]
	selected_set = set(selected_keys)
	adjacent, overflow = _fetch_edges(snapshot_doc.name, selected_keys)
	truncated |= overflow
	candidate_edges = [
		(edge.position, json.loads(edge.payload_json))
		for edge in adjacent
		if edge.source_key in selected_set and edge.target_key in selected_set
	]
	candidate_edges.sort(key=lambda item: item[0])
	return pack_context(
		metadata,
		snapshot_doc.project,
		query,
		selected,
		[edge for _, edge in candidate_edges],
		max_chars=max_chars,
		selection_truncated=truncated,
	)
