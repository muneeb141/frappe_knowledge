# Third-party notices and provenance

1. Frappe's v16 app-generator literal templates were used for the scaffold. The upstream MIT notice is preserved in `frappe-boilerplate/LICENSE`. The generator itself was not imported/executed and is not part of the runtime.
2. `frappe-skills/router/SKILL.md` and `frappe-skills/project-triage/SKILL.md` are unchanged reference copies from LUBUS at commit `afd9ea13afe8f3312e0dc53bcb483acac4ddf9ed`. Its MIT notice is included. This is a selected reference subset, not the full upstream skill package. Referenced skills may not be included. Do not install or auto-follow it as a complete package.
3. Three source files under `tests/fixtures/upstream/` are unchanged ERPNext/HRMS v16 research samples. Their upstream GPL license notices are preserved in the corresponding app folders. They are not imported by the runtime or unit tests; the indexer parses them as text/data.
4. FAC and Flow are evaluated integration candidates. Their runtime code and dependencies are not vendored or installed by this package.

Exact source URLs and Git blob hashes are in `provenance.json`. SHA-256 file hashes are generated in the sample snapshot. A blob hash identifies fetched content; the snapshot's own hash provides integrity, not a signature or independent proof of authorship.
