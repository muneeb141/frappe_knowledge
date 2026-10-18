# v16 implementation roadmap

This is the research starter's milestone map. The active local implementation phases and their verified status are in [`PLAN.md`](../PLAN.md).

## Milestone 0 — research and deterministic proof

Delivered in this package: architecture/reuse decisions, official-template-based app scaffold, two knowledge DocTypes and admin adapter source, bounded offline index/retrieval/diff commands, selected upstream skill references and real v16 source fixtures. Offline verification is recorded in STATUS.md. Bench/UI behavior remains unverified.

## Milestone 1 — prove the app on a real v16 bench

- Create or connect the Git repository; establish a disposable Python 3.14 / Node 24+ / Frappe v16 environment with the required database and queues.
- Install the app on a clean site, migrate, build assets, create a project, import the sample snapshot, and open the Desk page.
- Test admin import, denied non-admin access, project/snapshot authorization, duplicate imports, immutable snapshot behavior and malicious input rendering.
- Record exact installed app commits and environment versions. Resolve packaging and permission issues before adding a model.
- Exit: repeatable clean install and passing integration checks on the exact pinned environment.

## Milestone 2 — meaningful payroll knowledge

- Implement normalized evidence/node/edge persistence, scoped queries and background indexing.
- Expand from the three-file fixture to a reviewed payroll/accounting source slice, then include the required framework code, hooks and effective site metadata.
- Create manually verified workflow cases covering accrual creation, submit/cancel behavior, component/account settings and custom app overrides.
- Resolve relevant dynamic references; keep unknowns explicit.
- Exit: source-backed context finds required evidence on a held-out task set, with measured coverage and bounded latency.

## Milestone 3 — one model and coding-tool integration

- Select a provider/model and credential approach with the user before implementation of live API calls.
- Evaluate an optional Flow adapter and optional FAC/MCP integration against the same retrieval contract; choose by installed tests and measured effort/cost.
- Provide a simple dashboard: default model, optional role overrides, sources/refresh state, budget, usage and feedback.
- Answer support questions and propose source-backed change plans. Keep execution isolated and explicit.
- Exit: useful answers and plans outperform the baseline on consequential error rate without hiding costs or unknowns.

## Milestone 4 — reliable refresh and lessons

- Implement queued, idempotent incremental refresh with affected-record invalidation and atomic publication.
- Add automatic candidate capture, redaction, duplicate detection and evidence-backed lesson validation.
- Add permission-scoped caching, run accounting and per-project limits.
- Exit: updates preserve prior availability and lessons demonstrably prevent repeated mistakes on held-out cases.

## Milestone 5 — pilot and marketplace preparation

- Pilot with several independent Frappe implementers/support teams; measure value on their installations.
- Complete migrations/backup/restore/upgrade checks, installation docs, notices and operational requirements.
- Verify Frappe Cloud staging compatibility and marketplace requirements against current documentation.
- Exit: another team can install, configure, evaluate and operate it without the author's direct help.

Only after evidence from these milestones should scope expand to additional modules, agent roles, autonomous development or another major version. There is no v15/v14 implementation planned for the first release.

## Evaluation design

Use about 30 initial representative cases, then add a separate held-out set. Include straightforward questions, cross-app changes, configuration-dependent behavior, customizations, incompatible recommendations, source changes, authorization failures and insufficient-evidence questions. Keep ground truth with exact revisions and expected source/workflow facts.

Compare: (A) a capable coding assistant with direct repository access and good skills; (B) the same model with this context service; (C) optional orchestration only if it has a clear purpose. Hold model, task and allowed tools constant where possible.

Record answer correctness, critical dependency recall, wrong-version recommendations, unsupported claims, accepted/reworked changes, regression outcomes, latency and total cost per correctly completed task. Also record initialization and update costs. Do not market a token-savings percentage based only on a smaller prompt or one successful demonstration.
