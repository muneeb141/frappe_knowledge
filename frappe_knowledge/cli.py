"""Offline index, retrieve and compare commands; no model or network calls."""

import argparse
import json
import subprocess
from pathlib import Path

from frappe_knowledge.core.index import SourceRoot, build_snapshot, compare_snapshots, retrieve_context


def main(argv=None):
	parser = argparse.ArgumentParser(description=__doc__)
	sub = parser.add_subparsers(dest="command", required=True)
	index = sub.add_parser("index")
	index.add_argument("manifest", type=Path)
	index.add_argument("--output", required=True, type=Path)
	index.add_argument(
		"--fixture",
		action="store_true",
		help="Allow downloaded partial source samples without a Git checkout",
	)
	context = sub.add_parser("context")
	context.add_argument("snapshot", type=Path)
	context.add_argument("--project", required=True)
	context.add_argument("--query", required=True)
	context.add_argument("--max-chars", type=int, default=16000)
	context.add_argument("--profile", default="frappe-v16")
	diff = sub.add_parser("diff")
	diff.add_argument("before", type=Path)
	diff.add_argument("after", type=Path)
	diff.add_argument("--project", required=True)
	args = parser.parse_args(argv)
	if args.command == "index":
		manifest = json.loads(args.manifest.read_text())
		sources = []
		for item in manifest["sources"]:
			root = (args.manifest.parent / item["root"]).resolve()
			if not args.fixture:
				top = subprocess.run(
					["git", "rev-parse", "--show-toplevel"],
					cwd=root,
					check=True,
					capture_output=True,
					text=True,
					timeout=15,
				).stdout.strip()
				if Path(top).resolve() != root:
					raise ValueError("Source root must be the Git repository root")
				actual = subprocess.run(
					["git", "rev-parse", "HEAD"],
					cwd=root,
					check=True,
					capture_output=True,
					text=True,
					timeout=15,
				).stdout.strip()
				dirty = subprocess.run(
					["git", "status", "--porcelain", "--untracked-files=all"],
					cwd=root,
					check=True,
					capture_output=True,
					text=True,
					timeout=15,
				).stdout.strip()
				if actual != item["revision"] or dirty:
					raise ValueError("Source must be a clean checkout at the manifest revision")
			sources.append(
				SourceRoot(item["app"], item["repository"], item["revision"], root, item.get("version", ""))
			)
		result = build_snapshot(
			manifest["project_id"], sources, profile_id=manifest.get("profile_id", "frappe-v16")
		)
		# Fixture mode is deliberately visible and cannot be mistaken for a complete checkout.
		result["coverage"]["checkout_verified"] = not args.fixture
		result["coverage"]["fixture_mode"] = args.fixture
		from frappe_knowledge.core.index import _canonical, _digest

		result["snapshot_id"] = _digest(_canonical({k: v for k, v in result.items() if k != "snapshot_id"}))
		args.output.parent.mkdir(parents=True, exist_ok=True)
		args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
		print(
			json.dumps(
				{
					"snapshot_id": result["snapshot_id"],
					"files": len(result["files"]),
					"nodes": len(result["nodes"]),
					"edges": len(result["edges"]),
					"fixture_mode": args.fixture,
				}
			)
		)
		return
	if args.command == "context":
		result = retrieve_context(
			json.loads(args.snapshot.read_text()),
			args.project,
			args.query,
			profile_id=args.profile,
			max_chars=args.max_chars,
		)
	else:
		result = compare_snapshots(
			json.loads(args.before.read_text()), json.loads(args.after.read_text()), args.project
		)
	print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
