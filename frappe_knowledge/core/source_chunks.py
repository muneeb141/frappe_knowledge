"""Deterministic source excerpts derived from an immutable source snapshot."""

from pathlib import Path

from frappe_knowledge.core.index import _digest, _safe_path

MAX_CHUNK_CHARS = 3200
MAX_CHUNK_LINES = 45


def iter_source_chunks(snapshot, sources):
	"""Yield bounded text with exact file hash and line provenance.

	The source checkout is read as data only. A changed or escaped file aborts the
	projection instead of silently attaching text to the wrong snapshot.
	"""
	source_by_app = {source.app: source for source in sources}
	revisions = {source["app"]: source["revision"] for source in snapshot["sources"]}
	if set(source_by_app) != set(revisions):
		raise ValueError("Snapshot source set changed")
	for app, source in source_by_app.items():
		if source.revision != revisions[app]:
			raise ValueError("Snapshot source revision changed")
	for key, expected_hash in sorted(snapshot["files"].items()):
		app, separator, relative = key.partition(":")
		if not separator or app not in source_by_app:
			raise ValueError("Invalid snapshot file identity")
		root = source_by_app[app].root.resolve()
		path = root / _safe_path(relative)
		if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
			raise ValueError("Snapshot source file is unavailable")
		content = path.read_text(encoding="utf-8")
		if _digest(content) != expected_hash:
			raise ValueError("Snapshot source file changed")
		parts, length, start, end, number = [], 0, 1, 1, 0
		for line_number, line in enumerate(content.splitlines(keepends=True), 1):
			for offset in range(0, len(line), MAX_CHUNK_CHARS):
				segment = line[offset : offset + MAX_CHUNK_CHARS]
				if parts and (
					length + len(segment) > MAX_CHUNK_CHARS or line_number - start >= MAX_CHUNK_LINES
				):
					yield {
						"app": app,
						"path": relative,
						"file_sha256": expected_hash,
						"start_line": start,
						"end_line": end,
						"chunk_number": number,
						"content": "".join(parts),
					}
					parts, length, start, number = [], 0, line_number, number + 1
				if not parts:
					start = line_number
				parts.append(segment)
				length += len(segment)
				end = line_number
		if parts:
			yield {
				"app": app,
				"path": relative,
				"file_sha256": expected_hash,
				"start_line": start,
				"end_line": end,
				"chunk_number": number,
				"content": "".join(parts),
			}
