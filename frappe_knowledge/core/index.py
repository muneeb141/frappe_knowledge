"""Deterministic, bounded source indexing. This module never imports indexed code."""

from __future__ import annotations

import ast
import hashlib
import heapq
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote

SCHEMA_VERSION = 1
PROFILED_SCHEMA_VERSION = 2
DESCRIBED_SCHEMA_VERSION = 3
EXTRACTOR_VERSION = "0.3.0"
SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", "third_party"}
RELATIONS = {
	"LINK_FIELD",
	"CHILD_TABLE",
	"DYNAMIC_LINK_SELECTOR",
	"IMPORTS",
	"CONTROLLER_FOR",
	"CONTROLLER_MODULE_FOR",
	"USES_DOCTYPE",
}
RELATION_MEANINGS = {
	"LINK_FIELD": "A DocType declares a Link field pointing to another DocType; this does not prove a business workflow.",
	"CHILD_TABLE": "A DocType declares a child table field using another DocType.",
	"DYNAMIC_LINK_SELECTOR": "A Dynamic Link target depends on a selector value and needs runtime resolution.",
	"IMPORTS": "A Python module imports another module; this does not prove the imported code runs.",
	"CONTROLLER_FOR": "A Python class is in the conventional controller file for a DocType.",
	"CONTROLLER_MODULE_FOR": "A Python module is in the conventional controller file for a DocType; this does not prove every function runs.",
	"USES_DOCTYPE": "A Python call contains a literal DocType name; this does not prove the call runs.",
}
RELATION_PRIORITY = {
	"CONTROLLER_MODULE_FOR": 0,
	"USES_DOCTYPE": 1,
	"CONTROLLER_FOR": 2,
	"CHILD_TABLE": 3,
	"LINK_FIELD": 4,
	"IMPORTS": 5,
	"DYNAMIC_LINK_SELECTOR": 6,
}


@dataclass(frozen=True)
class SourceRoot:
	app: str
	repository: str
	revision: str
	root: Path
	version: str = ""

	def validate(self):
		if not re.fullmatch(r"[a-z][a-z0-9_]*", self.app):
			raise ValueError("Invalid app identifier")
		if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
			raise ValueError("Repository must be owner/name")
		if not re.fullmatch(r"[0-9a-f]{40}", self.revision):
			raise ValueError("A full immutable Git commit SHA is required")
		if not self.root.is_dir():
			raise ValueError("Source root is not a directory")


def _canonical(value):
	return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(value):
	return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalized_title(value):
	return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def walk_priority(relation, *, reverse=False):
	"""Prefer a controller's outgoing references over unrelated incoming callers."""
	penalty = 5 if reverse and relation in {"USES_DOCTYPE", "LINK_FIELD", "CHILD_TABLE"} else 0
	return RELATION_PRIORITY[relation] + penalty


def _safe_path(path):
	if not isinstance(path, str) or not path or "\\" in path:
		raise ValueError("Invalid source path")
	p = PurePosixPath(path)
	if p.is_absolute() or any(part in {"..", ".git"} for part in p.parts):
		raise ValueError("Source path must stay within the repository")
	return path


def _evidence(source, path, text, start=1, end=None):
	lines = text.splitlines()
	end = min(end or len(lines) or 1, len(lines) or 1)
	visible_end = min(start + 14, end)
	return {
		"app": source.app,
		"path": path,
		"revision": source.revision,
		"url": f"https://github.com/{source.repository}/blob/{source.revision}/{quote(path, safe='/')}#L{start}-L{visible_end}",
		"sha256": _digest(text),
		"start_line": start,
		"end_line": visible_end,
		"excerpt": "\n".join(lines[start - 1 : visible_end]),
		"excerpt_truncated": visible_end < end,
	}


def _source_description(value, source, path, text, start, end):
	"""Keep a bounded source-authored description and its own exact source lines."""
	if not isinstance(value, str) or not value.strip():
		return {}
	return {
		"source_description": " ".join(value.split())[:500],
		"description_status": "source_declared_unverified",
		"description_evidence": _evidence(source, path, text, start, end),
	}


def _doctype_description(data, source, path, text):
	description = data.get("description")
	if not isinstance(description, str) or not description.strip():
		return {}
	for match in re.finditer(r'"description"\s*:\s*("(?:\\.|[^"\\])*")', text):
		try:
			value = json.loads(match.group(1))
		except json.JSONDecodeError:
			continue
		if value == description:
			line = text.count("\n", 0, match.start()) + 1
			return _source_description(description, source, path, text, line, line)
	return {}


def _ast_description(tree, source, path, text):
	if (
		not tree.body
		or not isinstance(tree.body[0], ast.Expr)
		or not isinstance(tree.body[0].value, ast.Constant)
	):
		return {}
	docstring = ast.get_docstring(tree)
	if not docstring:
		return {}
	node = tree.body[0]
	return _source_description(docstring, source, path, text, node.lineno, node.end_lineno)


def build_snapshot(
	project_id,
	sources,
	*,
	profile_id="frappe-v16",
	max_files=20000,
	max_file_bytes=1000000,
	max_total_bytes=50000000,
):
	"""Index approved local source trees; source provenance is declared by the caller.

	A SourceRoot does not prove that a working tree matches its declared commit.
	The CLI checks clean Git checkouts unless explicit fixture mode is selected.
	"""
	if not isinstance(project_id, str) or not project_id.strip() or len(project_id) > 140:
		raise ValueError("A bounded project identifier is required")
	from frappe_knowledge.core.profiles import get_profile

	get_profile(profile_id)
	if not sources or len({s.app for s in sources}) != len(sources):
		raise ValueError("Exactly one source revision per app is required")
	for source in sources:
		source.validate()
	files, nodes, edges, issues = {}, {}, [], []
	total_bytes = 0
	doctypes, controller_files, pending_links, python_files = {}, {}, [], []
	for source in sorted(sources, key=lambda s: s.app):
		root = source.root.resolve()
		for path in sorted(root.rglob("*")):
			relative = path.relative_to(root)
			if set(relative.parts) & SKIP_DIRS or path.is_symlink() or not path.is_file():
				continue
			if path.suffix != ".py" and not (path.suffix == ".json" and "doctype" in relative.parts):
				continue
			if not path.resolve().is_relative_to(root):
				raise ValueError("Source escaped its root")
			if len(files) >= max_files:
				raise ValueError("File budget exceeded; narrow the source selection")
			key = f"{source.app}:{relative.as_posix()}"
			if path.stat().st_size > max_file_bytes:
				issues.append({"file": key, "reason": "file_size_limit"})
				continue
			text = path.read_text(encoding="utf-8")
			total_bytes += len(text.encode("utf-8"))
			if total_bytes > max_total_bytes:
				raise ValueError("Total source budget exceeded; narrow the source selection")
			rel = _safe_path(relative.as_posix())
			files[key] = _digest(text)
			if path.suffix == ".py":
				python_files.append((source, rel, text))
				continue
			try:
				data = json.loads(text)
			except json.JSONDecodeError:
				issues.append({"file": key, "reason": "invalid_json"})
				continue
			if not isinstance(data, dict) or data.get("doctype") != "DocType" or not data.get("name"):
				continue
			name = data["name"]
			if name in doctypes:
				raise ValueError(f"Duplicate DocType ownership: {name}")
			node_id = f"{source.app}:doctype:{name}"
			doctypes[name] = node_id
			controller_files[(source.app, rel.removesuffix(".json") + ".py")] = node_id
			nodes[node_id] = {
				"id": node_id,
				"kind": "doctype",
				"title": name,
				"app": source.app,
				"resolved": True,
				"evidence": _evidence(source, rel, text),
				**_doctype_description(data, source, rel, text),
			}
			for field in data.get("fields", []):
				kind, target = field.get("fieldtype"), field.get("options")
				if kind in {"Link", "Table", "Table MultiSelect"} and isinstance(target, str) and target:
					pending_links.append(
						(
							node_id,
							target,
							"LINK_FIELD" if kind == "Link" else "CHILD_TABLE",
							field.get("fieldname"),
							_evidence(source, rel, text),
						)
					)
				elif kind == "Dynamic Link":
					issues.append(
						{
							"file": key,
							"reason": "dynamic_link_requires_runtime_resolution",
							"field": field.get("fieldname"),
							"selector": target,
						}
					)

	def doctype_ref(name):
		node_id = doctypes.get(name, f"unresolved:doctype:{name}")
		if node_id not in nodes:
			nodes[node_id] = {"id": node_id, "kind": "doctype", "title": name, "app": "", "resolved": False}
		return node_id

	for node_id, target, relation, field, evidence in pending_links:
		edges.append(
			{
				"source": node_id,
				"target": doctype_ref(target),
				"relation": relation,
				"field": field,
				"evidence": evidence,
			}
		)
	for source, rel, text in python_files:
		try:
			tree = ast.parse(text)
		except SyntaxError:
			issues.append({"file": f"{source.app}:{rel}", "reason": "python_parse_error"})
			continue
		module_name = rel.removesuffix(".py").replace("/", ".")
		module_id = f"{source.app}:module:{module_name}"
		nodes[module_id] = {
			"id": module_id,
			"kind": "module",
			"title": module_name,
			"app": source.app,
			"resolved": True,
			"evidence": _evidence(source, rel, text),
			**_ast_description(tree, source, rel, text),
		}
		controller = controller_files.get((source.app, rel))
		if controller:
			edges.append(
				{
					"source": module_id,
					"target": controller,
					"relation": "CONTROLLER_MODULE_FOR",
					"evidence": nodes[module_id]["evidence"],
				}
			)
		for item in ast.walk(tree):
			if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
				# Line number disambiguates nested and repeated function names.
				identifier = f"{source.app}:symbol:{rel}:{item.lineno}:{item.name}"
				nodes[identifier] = {
					"id": identifier,
					"kind": "symbol",
					"title": item.name,
					"app": source.app,
					"resolved": True,
					"evidence": _evidence(source, rel, text, item.lineno, item.end_lineno),
					**_ast_description(item, source, rel, text),
				}
				if isinstance(item, ast.ClassDef):
					for node_id in doctypes.values():
						ev = nodes[node_id]["evidence"]
						if ev["app"] == source.app and ev["path"].removesuffix(".json") == rel.removesuffix(
							".py"
						):
							edges.append(
								{
									"source": identifier,
									"target": node_id,
									"relation": "CONTROLLER_FOR",
									"evidence": nodes[identifier]["evidence"],
								}
							)
			if isinstance(item, (ast.Import, ast.ImportFrom)):
				imports = (
					[a.name for a in item.names] if isinstance(item, ast.Import) else [item.module or ""]
				)
				for name in imports:
					if not name:
						continue
					app = name.split(".")[0]
					target = f"{app}:module:{name}"
					nodes.setdefault(
						target, {"id": target, "kind": "module", "title": name, "app": app, "resolved": False}
					)
					edges.append(
						{
							"source": module_id,
							"target": target,
							"relation": "IMPORTS",
							"evidence": _evidence(source, rel, text, item.lineno, item.end_lineno),
						}
					)
			if isinstance(item, ast.Call):
				target = None
				call = ast.unparse(item.func)
				if (
					call
					in {
						"frappe.get_doc",
						"frappe.new_doc",
						"frappe.get_list",
						"frappe.get_all",
						"frappe.db.get_value",
						"frappe.db.get_all",
						"frappe.db.get_list",
						"frappe.db.exists",
						"frappe.db.count",
					}
					and item.args
				):
					first = item.args[0]
					if isinstance(first, ast.Constant) and isinstance(first.value, str):
						target = first.value
					elif isinstance(first, ast.Dict):
						for k, v in zip(first.keys, first.values, strict=True):
							if (
								isinstance(k, ast.Constant)
								and k.value == "doctype"
								and isinstance(v, ast.Constant)
								and isinstance(v.value, str)
							):
								target = v.value
				if target:
					edges.append(
						{
							"source": module_id,
							"target": doctype_ref(target),
							"relation": "USES_DOCTYPE",
							"evidence": _evidence(source, rel, text, item.lineno, item.end_lineno),
						}
					)
	# Resolve imported modules after every source has been visited; never replace indexed evidence with placeholders.
	edges = sorted(
		{_canonical(e): e for e in edges}.values(),
		key=lambda e: (e["source"], e["target"], e["relation"], e["evidence"]["start_line"]),
	)
	result = {
		"schema_version": DESCRIBED_SCHEMA_VERSION,
		"extractor_version": EXTRACTOR_VERSION,
		"project_id": project_id,
		"profile_id": profile_id,
		"sources": [
			{"app": s.app, "repository": s.repository, "revision": s.revision, "version": s.version}
			for s in sorted(sources, key=lambda s: s.app)
		],
		"coverage": {
			"status": "partial",
			"extractors": [
				"doctype_link_fields",
				"python_imports",
				"literal_doctype_calls",
				"controller_convention",
				"controller_module_convention",
			],
			"limitations": [
				"No JavaScript or dynamic call resolution",
				"No workflow, permissions, hooks or business-rule inference",
				"Declared revisions require checkout verification",
			],
		},
		"files": dict(sorted(files.items())),
		"nodes": sorted(nodes.values(), key=lambda n: n["id"]),
		"edges": edges,
		"issues": issues,
	}
	result["snapshot_id"] = _digest(_canonical(result))
	return result


def snapshot_profile(snapshot):
	"""Schema 1 has only ever represented the original Frappe v16 corpus."""
	if snapshot.get("schema_version") == SCHEMA_VERSION and "profile_id" not in snapshot:
		return "frappe-v16"
	if snapshot.get("schema_version") in {PROFILED_SCHEMA_VERSION, DESCRIBED_SCHEMA_VERSION}:
		return snapshot.get("profile_id")
	raise ValueError("Unsupported snapshot schema")


def validate_snapshot(snapshot, project_id, *, profile_id=None):
	if (
		snapshot.get("schema_version")
		not in {SCHEMA_VERSION, PROFILED_SCHEMA_VERSION, DESCRIBED_SCHEMA_VERSION}
		or snapshot.get("project_id") != project_id
	):
		raise ValueError("Unsupported schema or project mismatch")
	actual_profile = snapshot_profile(snapshot)
	from frappe_knowledge.core.profiles import get_profile

	get_profile(actual_profile)
	if profile_id is not None and actual_profile != profile_id:
		raise ValueError("Snapshot profile mismatch")
	expected = snapshot.get("snapshot_id")
	actual = _digest(_canonical({k: v for k, v in snapshot.items() if k != "snapshot_id"}))
	if not isinstance(expected, str) or expected != actual:
		raise ValueError("Snapshot integrity check failed")
	source_map = {s["app"]: s for s in snapshot["sources"]}
	if len(source_map) != len(snapshot["sources"]):
		raise ValueError("Duplicate app source")
	for s in source_map.values():
		if not re.fullmatch(r"[0-9a-f]{40}", s["revision"]):
			raise ValueError("Mutable source revision")
		if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", s["repository"]):
			raise ValueError("Invalid repository")
	ids = {n["id"] for n in snapshot["nodes"]}
	if len(ids) != len(snapshot["nodes"]):
		raise ValueError("Duplicate node")
	for e in snapshot["edges"]:
		if e["source"] not in ids or e["target"] not in ids or e["relation"] not in RELATIONS:
			raise ValueError("Invalid dependency edge")
	for item in [*snapshot["nodes"], *snapshot["edges"]]:
		ev = item.get("evidence")
		if ev:
			s = source_map[ev["app"]]
			path = _safe_path(ev["path"])
			expected_url = f"https://github.com/{s['repository']}/blob/{s['revision']}/{quote(path, safe='/')}#L{ev['start_line']}-L{ev['end_line']}"
			if (
				ev["revision"] != s["revision"]
				or ev["url"] != expected_url
				or snapshot["files"].get(f"{ev['app']}:{path}") != ev["sha256"]
			):
				raise ValueError("Evidence is inconsistent with its source")
		description_evidence = item.get("description_evidence")
		if description_evidence:
			source = source_map[description_evidence["app"]]
			path = _safe_path(description_evidence["path"])
			expected_url = f"https://github.com/{source['repository']}/blob/{source['revision']}/{quote(path, safe='/')}#L{description_evidence['start_line']}-L{description_evidence['end_line']}"
			if (
				description_evidence["revision"] != source["revision"]
				or description_evidence["url"] != expected_url
				or snapshot["files"].get(f"{description_evidence['app']}:{path}")
				!= description_evidence["sha256"]
			):
				raise ValueError("Description evidence is inconsistent with its source")
	return snapshot


def retrieve_context(
	snapshot, project_id, query, *, profile_id=None, max_nodes=20, max_chars=16000, max_hops=2
):
	validate_snapshot(snapshot, project_id, profile_id=profile_id)
	if not isinstance(query, str) or not query.strip() or len(query) > 500:
		raise ValueError("Query must contain 1-500 characters")
	if not 1 <= max_nodes <= 50 or not 2000 <= max_chars <= 64000 or not 0 <= max_hops <= 3:
		raise ValueError("Context budget is out of range")
	terms = set(re.findall(r"[a-z0-9]+", query.lower()))

	def score(n):
		words = set(re.findall(r"[a-z0-9]+", n["title"].lower()))
		return len(terms & words) * (5 if n["kind"] == "doctype" else 1)

	ranked = sorted(
		(n for n in snapshot["nodes"] if n["resolved"] and score(n)), key=lambda n: (-score(n), n["id"])
	)
	exact = [n for n in ranked if normalized_title(n["title"]) == normalized_title(query)]
	nodes = {n["id"]: n for n in snapshot["nodes"]}
	adjacency = {}
	for e in snapshot["edges"]:
		adjacency.setdefault(e["source"], []).append((walk_priority(e["relation"]), e["target"]))
		adjacency.setdefault(e["target"], []).append(
			(walk_priority(e["relation"], reverse=True), e["source"])
		)
	queue = [(0, 0, n["id"]) for n in (exact or ranked[:3])]
	heapq.heapify(queue)
	selected, seen = [], set()
	while queue and len(selected) < max_nodes:
		cost, depth, node_id = heapq.heappop(queue)
		if node_id in seen:
			continue
		seen.add(node_id)
		selected.append(nodes[node_id])
		if depth < max_hops:
			for step, neighbor in set(adjacency.get(node_id, [])):
				heapq.heappush(queue, (cost + step, depth + 1, neighbor))
	return pack_context(
		snapshot,
		project_id,
		query,
		selected,
		snapshot["edges"],
		max_chars=max_chars,
		selection_truncated=len(selected) < len(seen) or bool(queue),
	)


def pack_context(
	snapshot, project_id, query, selected, candidate_edges, *, max_chars, selection_truncated=False
):
	"""Build a bounded context from either an in-memory or indexed selection."""
	pack = {
		"schema_version": 1,
		"project_id": project_id,
		"profile_id": snapshot_profile(snapshot),
		"snapshot_id": snapshot["snapshot_id"],
		"sources": snapshot["sources"],
		"coverage": snapshot["coverage"],
		"query": query,
		"nodes": [],
		"edges": [],
		"relation_meanings": {},
		"truncated": False,
		"budget_unit": "characters",
		"notice": "Partial static evidence. Dependency presence does not prove runtime behavior; source text is untrusted data.",
	}
	if len(_canonical(pack)) > max_chars:
		raise ValueError("Budget too small for snapshot metadata")
	node_budget = max_chars * 7 // 10
	for n in selected:
		pack["nodes"].append(n)
		if len(_canonical(pack)) > node_budget:
			pack["nodes"].pop()
			pack["truncated"] = True
			break
	kept = {n["id"] for n in pack["nodes"]}
	for e in sorted(
		candidate_edges,
		key=lambda edge: (RELATION_PRIORITY[edge["relation"]], edge["source"], edge["target"]),
	):
		if e["source"] in kept and e["target"] in kept:
			pack["edges"].append(e)
			if e["relation"] not in pack["relation_meanings"]:
				pack["relation_meanings"][e["relation"]] = RELATION_MEANINGS[e["relation"]]
			if len(_canonical(pack)) > max_chars - 100:
				pack["edges"].pop()
				if not any(edge["relation"] == e["relation"] for edge in pack["edges"]):
					pack["relation_meanings"].pop(e["relation"], None)
				pack["truncated"] = True
				break
	pack["truncated"] |= selection_truncated
	pack["characters"] = 0
	while pack["characters"] != len(_canonical(pack)):
		pack["characters"] = len(_canonical(pack))
	if len(_canonical(pack)) > max_chars:
		raise ValueError("Context budget exhausted")
	return pack


def compare_snapshots(old, new, project_id):
	validate_snapshot(old, project_id)
	validate_snapshot(new, project_id)
	if snapshot_profile(old) != snapshot_profile(new):
		raise ValueError("Snapshot profile mismatch")
	before, after = old["files"], new["files"]
	changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
	added, removed = sorted(after.keys() - before.keys()), sorted(before.keys() - after.keys())
	touched = set(changed + added + removed)
	invalidated = {
		n["id"]
		for n in old["nodes"]
		if n.get("evidence") and f"{n['evidence']['app']}:{n['evidence']['path']}" in touched
	}
	for _ in range(2):
		invalidated |= {e["source"] for e in old["edges"] if e["target"] in invalidated}
	return {
		"project_id": project_id,
		"old_snapshot": old["snapshot_id"],
		"new_snapshot": new["snapshot_id"],
		"added": added,
		"changed": changed,
		"removed": removed,
		"invalidate_nodes": sorted(invalidated),
		"rebuild_required": old["extractor_version"] != new["extractor_version"],
		"notice": "A diff plan, not a complete business-impact analysis or automatic deployment.",
	}
