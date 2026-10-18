"""Safe preflight: report tool versions, never credentials or configuration values."""

import json
import shutil
import subprocess
import sys

checks = {"python": {"version": sys.version.split()[0], "meets_v16": sys.version_info[:2] == (3, 14)}}
for tool, args in {
	"node": ["--version"],
	"bench": ["--version"],
	"redis-server": ["--version"],
	"mariadb": ["--version"],
}.items():
	executable = shutil.which(tool)
	result = {"present": bool(executable)}
	if executable:
		process = subprocess.run([executable, *args], capture_output=True, text=True, timeout=10)
		result["version"] = (process.stdout or process.stderr).strip().splitlines()[0][:200]
	checks[tool] = result
if checks["node"]["present"]:
	try:
		checks["node"]["meets_v16"] = int(checks["node"]["version"].lstrip("v").split(".")[0]) >= 24
	except (KeyError, ValueError):
		checks["node"]["meets_v16"] = False
ready = (
	checks["python"]["meets_v16"]
	and checks["node"].get("meets_v16", False)
	and all(checks[t]["present"] for t in ("bench", "redis-server", "mariadb"))
)
print(json.dumps({"ready_for_bench_setup": ready, "checks": checks}, indent=2))
raise SystemExit(0 if ready else 1)
