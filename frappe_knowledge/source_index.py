"""Rebuildable, snapshot-scoped source text search for verified local checkouts."""

import json
import re
from urllib.parse import quote

import frappe

from frappe_knowledge.core.index import _canonical, _digest, _safe_path, normalized_title
from frappe_knowledge.core.source_chunks import iter_source_chunks

CHUNK_FIELDS = [
	"name",
	"snapshot",
	"source_app",
	"source_path",
	"file_sha256",
	"chunk_number",
	"start_line",
	"end_line",
	"content",
	"search_text",
]
MAX_SEARCH_HITS = 8
SEARCH_STOPWORDS = {
	"a",
	"an",
	"are",
	"can",
	"does",
	"do",
	"for",
	"from",
	"how",
	"in",
	"is",
	"it",
	"of",
	"the",
	"to",
	"what",
	"when",
	"where",
	"which",
	"who",
	"with",
}


def _search_text(content):
	"""Keep source intact while making snake_case and camelCase words searchable."""
	return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", content.replace("_", " "))


def write_source_chunks(snapshot, sources):
	"""Write a derived projection only when local bytes match snapshot file hashes."""
	snapshot_id = snapshot["snapshot_id"]
	stored = frappe.db.get_value("FK Snapshot", snapshot_id, "source_chunks") or 0
	if stored:
		if frappe.db.count("FK Source Chunk", {"snapshot": snapshot_id}) != stored:
			raise ValueError("Stored source chunk count does not match")
		return stored
	expected = 0

	def rows():
		nonlocal expected
		for chunk in iter_source_chunks(snapshot, sources):
			expected += 1
			key = f"{snapshot_id}:{chunk['app']}:{chunk['path']}:{chunk['chunk_number']}"
			yield (
				_digest(key),
				snapshot_id,
				chunk["app"],
				chunk["path"],
				chunk["file_sha256"],
				chunk["chunk_number"],
				chunk["start_line"],
				chunk["end_line"],
				chunk["content"],
				_search_text(chunk["content"]),
			)

	frappe.db.bulk_insert("FK Source Chunk", CHUNK_FIELDS, rows(), ignore_duplicates=True, chunk_size=200)
	actual = frappe.db.count("FK Source Chunk", {"snapshot": snapshot_id})
	if actual != expected:
		raise ValueError("Source chunk count does not match the snapshot")
	frappe.db.set_value("FK Snapshot", snapshot_id, "source_chunks", actual, update_modified=False)
	return actual


def _lexical_query(query):
	words = re.findall(r"[A-Za-z0-9]+", _search_text(query))
	return " ".join(
		word.lower() for word in words if len(word) >= 3 and word.lower() not in SEARCH_STOPWORDS
	)[:500]


def search_source_chunks(snapshot_doc, query):
	"""Return only chunks from an already-authorized snapshot."""
	if not snapshot_doc.source_chunks:
		return [], False
	search = _lexical_query(query)
	if not search:
		return [], False
	rows = frappe.db.sql(
		"SELECT source_app, source_path, file_sha256, chunk_number, start_line, end_line, content, "
		"MATCH(search_text) AGAINST (%s IN NATURAL LANGUAGE MODE) AS relevance, "
		"CASE WHEN source_path REGEXP '(^|/)test_[^/]*[.]py$' THEN 1 ELSE 0 END AS is_test "
		"FROM `tabFK Source Chunk` WHERE snapshot = %s "
		"AND MATCH(search_text) AGAINST (%s IN NATURAL LANGUAGE MODE) "
		"ORDER BY is_test, relevance DESC, source_app, source_path, start_line, chunk_number LIMIT %s",
		(search, snapshot_doc.name, search, 101),
		as_dict=True,
	)
	strongest = next((row for row in rows if not row.is_test), None)
	module_match = next(
		(
			row
			for row in rows
			if not row.is_test
			and row.source_path.endswith(".py")
			and not any(part in row.source_path for part in ("/doctype/", "/patches/", "/report/"))
			and not row.source_path.endswith("/__init__.py")
		),
		None,
	)
	terms = set(search.split())

	def path_terms(row):
		return set(re.findall(r"[a-z0-9]+", row.source_path.lower().replace("_", " ")))

	def source_tier(row):
		path = row.source_path
		if "/doctype/" in path:
			return 0
		if "/patches/" in path:
			return 3
		if "/report/" in path:
			return 2
		return 1

	rows.sort(
		key=lambda row: (
			row.is_test,
			-len(terms & path_terms(row)),
			source_tier(row),
			-row.relevance,
			row.source_app,
			row.source_path,
			row.start_line,
		)
	)
	ranked_files = []
	seen_files = set()
	for row in rows:
		file_key = (row.source_app, row.source_path)
		if file_key in seen_files:
			continue
		seen_files.add(file_key)
		ranked_files.append(row)
	# Location questions benefit from one high-scoring module implementation
	# alongside DocType controllers. Retain the best existing result and avoid
	# promoting a weak module solely to fill the diversity slot.
	if (
		query.lstrip().lower().startswith("where ")
		and strongest
		and module_match
		and module_match.relevance >= strongest.relevance * 0.7
		and ranked_files
	):
		module_key = (module_match.source_app, module_match.source_path)
		if (ranked_files[0].source_app, ranked_files[0].source_path) != module_key:
			ranked_files = [
				ranked_files[0],
				module_match,
				*(row for row in ranked_files[1:] if (row.source_app, row.source_path) != module_key),
			]
	matches = [_source_match(snapshot_doc, row) for row in ranked_files[:MAX_SEARCH_HITS]]
	return matches, len(rows) > MAX_SEARCH_HITS


def _source_match(snapshot_doc, row):
	metadata = json.loads(snapshot_doc.metadata_json)
	source_by_app = {source["app"]: source for source in metadata["sources"]}
	source = source_by_app[row.source_app]
	path = _safe_path(row.source_path)
	file_row = frappe.db.get_value(
		"FK Knowledge Row",
		{
			"snapshot": snapshot_doc.name,
			"row_kind": "File",
			"lookup_key": _digest(f"{row.source_app}:{path}"),
		},
		"payload_json",
	)
	if not file_row or json.loads(file_row)["sha256"] != row.file_sha256:
		raise ValueError("Source chunk file identity does not match the snapshot")
	return {
		"app": row.source_app,
		"path": path,
		"revision": source["revision"],
		"sha256": row.file_sha256,
		"start_line": row.start_line,
		"end_line": row.end_line,
		"url": f"https://github.com/{source['repository']}/blob/{source['revision']}/{quote(path, safe='/')}#L{row.start_line}-L{row.end_line}",
		"content": row.content,
		"excerpt_truncated": False,
		"status": "source_text_unverified",
	}


def _exact_node_chunk(snapshot_doc, context, query):
	exact = next(
		(node for node in context["nodes"] if normalized_title(node["title"]) == normalized_title(query)),
		None,
	)
	if exact is None:
		nodes = frappe.db.sql(
			"SELECT node.payload_json FROM `tabFK Knowledge Row` exact_row "
			"JOIN `tabFK Knowledge Row` node ON node.snapshot = exact_row.snapshot "
			"AND node.row_kind = 'Node' AND node.lookup_key = exact_row.source_key "
			"WHERE exact_row.snapshot = %s AND exact_row.row_kind = 'Exact' "
			"AND exact_row.lookup_key = %s ORDER BY node.lookup_key LIMIT 1",
			(snapshot_doc.name, _digest(normalized_title(query))),
			as_dict=True,
		)
		exact = json.loads(nodes[0].payload_json) if nodes else None
	evidence = exact.get("evidence") if exact else None
	if not evidence:
		return None
	rows = frappe.db.sql(
		"SELECT source_app, source_path, file_sha256, chunk_number, start_line, end_line, content "
		"FROM `tabFK Source Chunk` WHERE snapshot = %s AND file_sha256 = %s "
		"AND start_line <= %s AND end_line >= %s ORDER BY chunk_number LIMIT 1",
		(snapshot_doc.name, evidence["sha256"], evidence["start_line"], evidence["start_line"]),
		as_dict=True,
	)
	return _source_match(snapshot_doc, rows[0]) if rows else None


def _shorten_match(match, query, length):
	original = match["content"]
	term = query.lower()
	location = original.lower().find(term)
	if location < 0:
		location = next(
			(
				original.lower().find(word)
				for word in _lexical_query(query).split()
				if original.lower().find(word) >= 0
			),
			0,
		)
	start = min(max(0, location - length // 3), max(0, len(original) - length))
	window = original[start : start + length]
	start_line = match["start_line"] + original[:start].count("\n")
	end_line = start_line + window.count("\n") - int(window.endswith("\n"))
	end_line = max(start_line, end_line)
	return {
		**match,
		"content": window,
		"start_line": start_line,
		"end_line": end_line,
		"url": f"{match['url'].split('#L')[0]}#L{start_line}-L{end_line}",
		"excerpt_truncated": True,
	}


def attach_source_matches(snapshot_doc, context, query, max_chars):
	"""Add cited search results while preserving the caller's hard character budget."""

	def recount():
		for _ in range(4):
			size = len(_canonical(context))
			if context.get("characters") == size:
				break
			context["characters"] = size

	context["source_index"] = "available" if snapshot_doc.source_chunks else "unavailable"
	context["source_matches"] = []
	matches, overflow = search_source_chunks(snapshot_doc, query)
	exact_chunk = _exact_node_chunk(snapshot_doc, context, query)
	if exact_chunk:
		matches = [
			exact_chunk,
			*(
				match
				for match in matches
				if (match["app"], match["path"], match["start_line"])
				!= (exact_chunk["app"], exact_chunk["path"], exact_chunk["start_line"])
			),
		]
	for match in matches:
		length = len(match["content"])
		while True:
			candidate = match if length == len(match["content"]) else _shorten_match(match, query, length)
			context["source_matches"].append(candidate)
			recount()
			if context["characters"] <= max_chars:
				break
			context["source_matches"].pop()
			if length <= 300:
				overflow = True
				break
			length = int(length * 0.8)
		if context["characters"] > max_chars:
			break
	context["truncated"] |= overflow
	recount()
	return context
