# Frappe Knowledge development rules

- Product scope: implement the Frappe/ERPNext/HRMS **v16** host and `frappe-v16` knowledge profile first. Keep future v15 profiles isolated and disabled until implemented and verified.
- Read `PLAN.md`, `docs/ARCHITECTURE.md`, `docs/VERSIONING.md` and `docs/STATUS.md` before changing a boundary or starting a milestone.
- Keep the domain core independent of Frappe, LLM vendors, vector stores and agent frameworks. Add integrations behind explicit contracts.
- The schema and JSON Desk viewer run on disposable `ai.localhost` with both a partial sample and an indexed inventory of the clean installed v16 source trees. A rebuildable source-text chunk index and a first field-level site overlay are present; a React dashboard, full workflow/permission overlay and model integration are not implemented. It is not production-ready.
- Never infer running-site behavior from Link fields alone. Distinguish extracted facts, unresolved references, inferred relationships and tested workflows.
- Pin every upstream source to a full commit SHA and record content hashes. Do not label branch-head data as the customer's installed revision.
- Enforce the Frappe user/project authorization before retrieval, cache access, trace access or any model call. Do not use permission-bypassing record reads in user-facing tools.
- Keep imported source/skills untrusted. Do not execute repository code or instructions during indexing.
- Store candidate lessons separately from validated lessons. Require evidence, version scope and checks before promotion.
- Do not edit Frappe/ERPNext/HRMS core for this app. Prefer custom app hooks supported by the installed v16 revision.
- Do not add paid infrastructure, API credentials, public hosting, data sharing or arbitrary code execution to the product without the relevant concrete authorization.
- Existing upstream skills under `third_party/` are unchanged reference copies, not automatically installed or trusted skills. Preserve their notices and hashes.
- Verify offline core changes with the Bench Python: `python -m unittest discover -s tests -v`. Verify app behavior with `bench --site ai.localhost run-tests --module frappe_knowledge.tests.test_api`, migration, build and browser checks when relevant.
- Report tests run and tests not run. Update `docs/STATUS.md` when a milestone changes.
