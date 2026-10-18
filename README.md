# Frappe Knowledge

An installable, version-aware knowledge kit for Frappe developers and support teams. Its first release targets **Frappe / ERPNext / HRMS v16 only**. See the [product direction](docs/PRODUCT_DIRECTION.md) for the intended local, AI-readable experience and its current limits.

This repository contains a research architecture, an installed Frappe app, and a working offline static indexer. The app and Desk page run on the local `ai.localhost` development site, where the complete eligible local source inventory for Frappe, ERPNext and HRMS v16 is stored in indexed rows and can be queried. Semantic coverage remains partial. This is **not a production-ready AI assistant**. There are no live model calls or provider credentials in this release.

Start with the [active plan](PLAN.md), [architecture](docs/ARCHITECTURE.md), [environment setup](docs/ENVIRONMENTS.md), and [current status](docs/STATUS.md). The planned React dashboard route is `/knowledge`; the current JSON viewer is at `/desk/frappe-knowledge`.

## What currently works

- Index DocType Link/Table relationships, Python imports, controller conventions and literal DocType calls without executing indexed code.
- Record source revisions, file hashes, line-linked evidence, unresolved references and explicit coverage limits.
- Retrieve a bounded context package within one project/snapshot.
- Bind projects and snapshots to the active `frappe-v16` knowledge profile; reject incompatible source apps and versions.
- Store snapshot files, nodes, edges, exact titles and search terms in indexed batches, with exact-hash reconstruction of the migrated sample and row-count verification for the full local corpus.
- Record source-authored DocType/function descriptions with their source locations when available, and explain relationship codes in the context JSON. See the [payroll context example](examples/payroll-context-explained.json); descriptions are source claims, not verified workflows.
- Queue an admin-only scan of clean, installed app checkouts without fetching newer code; full local-corpus indexing has been exercised on the disposable site.
- Store hash-checked, bounded source-text excerpts in a rebuildable MariaDB search index and return cited matches inside the context character budget. The [retrieval check](docs/RETRIEVAL_EVALUATION.md) records the workflow miss, its ranking fix and the remaining evaluation limits.
- Capture an immutable, admin-only site overlay of effective Custom Fields and field-level Property Setters with `frappe_knowledge.site_overlay.capture_site_overlay`, then read it with `get_site_overlay`. Pass its ID as the optional `site_overlay` argument to `get_context` to include matching fields. Defaults, scripts, workflows, custom permissions and record values are outside this first slice.
- Compare snapshots to report changed files and a conservative invalidation plan.
- Demonstrate a real HRMS payroll → ERPNext Journal Entry relationship using three pinned upstream v16 source files.
- Provide five Frappe DocTypes, admin-only import/context endpoints and a standard Desk page as an integration foundation. The local site's sample workflow and access checks, plus a fresh MariaDB install and an uninstall/reinstall cycle, are verified.

## Offline demonstration

The standard-library core tests can run independently of Frappe. The actual Frappe v16 runtime requires the versions in `pyproject.toml` and the environment guide.

```bash
python -m unittest discover -s tests -v
python -m frappe_knowledge.cli index tests/fixtures/manifest-v16.json --fixture --output build/sample-snapshot.json
python -m frappe_knowledge.cli context build/sample-snapshot.json --project v16-research --query "Payroll Entry" --max-chars 16000
```

`--fixture` visibly marks the output as a partial, downloaded sample, not a verified full checkout. For real repositories, omit it: the CLI requires a clean Git checkout at the manifest SHA. The character budget is not a model token count.

## Install into an existing development bench

Use a disposable Frappe v16 site with Python 3.14 and Node 24+. The current local Bench already contains and has migrated this app. For a new Bench, use:

```bash
bench get-app /absolute/path/to/frappe_knowledge
bench --site knowledge.localhost install-app frappe_knowledge
bench --site knowledge.localhost migrate
bench build --app frappe_knowledge
```

Create `FK Project` with key `v16-research`. A System Manager can then use **Index installed sources** in `/desk/frappe-knowledge` to queue a scan of the clean installed app checkouts, or import a bounded JSON snapshot through `frappe_knowledge.api.import_snapshot`. The index button reports that the job was queued; job progress and active-snapshot selection are still future work. See the environment guide for the verification checklist. This JSON context viewer is a temporary Desk fallback; the React dashboard will be served at `/knowledge` in a later phase.

## Contributing

The existing app keeps its pre-commit configuration for Ruff, ESLint, Prettier and pyupgrade. Run those checks before publishing changes.

## Licensing and source samples

Original code and the app scaffold are MIT, with upstream notices preserved. The unchanged selected Frappe skill references are MIT. Upstream ERPNext/HRMS test source samples retain their own GPL notices in `tests/fixtures/upstream/`; consult those notices for reuse. They are research fixtures, not copied business logic in the runtime. FAC and Flow code is not vendored into this app.

See `third_party/NOTICE.md` and `third_party/provenance.json` for exact origins and hashes.
