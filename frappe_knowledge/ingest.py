"""Index clean, installed source apps without a network request or user-supplied path."""

import re
import subprocess
from pathlib import Path

import frappe
from frappe.utils import get_app_version

from frappe_knowledge.core.index import SourceRoot, _canonical, _digest, build_snapshot, validate_snapshot
from frappe_knowledge.core.profiles import get_profile, validate_sources


def _git(root, *args):
	result = subprocess.run(
		["git", "-C", str(root), *args], capture_output=True, text=True, check=True, timeout=20
	)
	return result.stdout.strip()


def installed_source_roots(profile_id):
	"""Resolve only registered, installed apps at their actual clean local commits."""
	profile = get_profile(profile_id)
	installed = set(frappe.get_installed_apps())
	sources = []
	for rule in profile.apps:
		if rule.app not in installed:
			continue
		root = Path(frappe.get_app_source_path(rule.app)).resolve()
		if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
			raise ValueError(f"{rule.app} source is not a Git repository root")
		if _git(root, "status", "--porcelain", "--untracked-files=all"):
			raise ValueError(f"{rule.app} source has local changes")
		revision = _git(root, "rev-parse", "HEAD")
		if not re.fullmatch(r"[0-9a-f]{40}", revision):
			raise ValueError(f"{rule.app} has no immutable Git revision")
		sources.append(SourceRoot(rule.app, rule.repository, revision, root, get_app_version(rule.app)))
	validate_sources(
		profile_id,
		[
			{"app": source.app, "repository": source.repository, "version": source.version}
			for source in sources
		],
	)
	return sources


def run_local_index(project):
	"""Worker entry point. Publication is one Frappe transaction, with no active-pointer change."""
	from frappe_knowledge.api import _store_snapshot
	from frappe_knowledge.source_index import write_source_chunks

	project_doc = frappe.get_doc("FK Project", project)
	sources = installed_source_roots(project_doc.knowledge_profile)
	snapshot = build_snapshot(project_doc.name, sources, profile_id=project_doc.knowledge_profile)
	snapshot["coverage"].update(
		{
			"checkout_verified": True,
			"repository_identity": "declared_by_profile",
			"source_mode": "installed_local_checkout",
		}
	)
	snapshot["snapshot_id"] = _digest(_canonical({k: v for k, v in snapshot.items() if k != "snapshot_id"}))
	validate_snapshot(snapshot, project_doc.name, profile_id=project_doc.knowledge_profile)
	name = _store_snapshot(project_doc, snapshot, verify_roundtrip=False)
	write_source_chunks(snapshot, sources)
	return name


@frappe.whitelist(methods=["POST"])
def request_local_index(project):
	"""Queue a local scan. It never pulls, updates, or executes indexed repositories."""
	frappe.only_for("System Manager")
	project_doc = frappe.get_doc("FK Project", project)
	project_doc.check_permission("write")
	get_profile(project_doc.knowledge_profile)
	job_id = f"frappe-knowledge-local-index-{project_doc.name}"
	frappe.enqueue(
		"frappe_knowledge.ingest.run_local_index",
		queue="long",
		timeout=3600,
		enqueue_after_commit=True,
		job_id=job_id,
		deduplicate=True,
		project=project_doc.name,
	)
	return {"job_id": job_id, "status": "queued_or_running", "source": "installed_local_checkout"}
