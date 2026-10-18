# Research and open-source reuse

The follow-up [storage and indexing decision](STORAGE_AND_INDEXING.md) compares the current JSON/row store with MariaDB full-text search, LanceDB, vectors, LiteLLM and LlamaIndex, and records the gates for adding more source apps.
The clarified [product direction](PRODUCT_DIRECTION.md) compares the intended local source-evidence kit with Flow's agent/RAG layer and FAC's permission-scoped tool/MCP layer. Their published capabilities overlap with the proposed chat and integrations, so the version-pinned cross-app knowledge value must be tested rather than assumed.

Checked 18 October 2026. The user selected **v16 only** during this work; earlier v15 analysis is superseded for implementation scope. Capability statements below come from project source/docs, not an installed benchmark.

## Findings that changed the design

1. Frappe Flow already covers much of the proposed agent/model/tool/knowledge dashboard. Its current package targets Frappe `>=16.0.0-dev,<18.0.0`, Python `>=3.14,<3.15`, and includes LiteLLM and LanceDB. It becomes a candidate now that v16 is the starting version. It should not own the application's knowledge schema or be installed blindly as an assumed lightweight dependency. [Package source](https://github.com/frappe/flow_client/blob/4a3189b6cbef0cad8ed16b24220d11242672996b/pyproject.toml), [project](https://github.com/frappe/flow_client).
2. FAC already has live effective schema access, reusable on-demand skills and external-app tool/skill hooks. Its package declares version 3.1.0, Python >=3.10, an AGPL license, a pinned assistant runtime SDK, and a substantial dependency set. Its README separates the external-client MCP path from its managed in-Frappe chat service. Reuse its supported integration surface rather than copying its chat product or assuming its in-app UI accepts arbitrary provider keys. [README](https://github.com/buildswithpaul/Frappe_Assistant_Core/blob/3a7a0b4a3bf589334d7816065377e8cbbd4e5cd9/README.md), [external app guide](https://github.com/buildswithpaul/Frappe_Assistant_Core/blob/3a7a0b4a3bf589334d7816065377e8cbbd4e5cd9/docs/development/EXTERNAL_APP_DEVELOPMENT.md), [skills guide](https://github.com/buildswithpaul/Frappe_Assistant_Core/blob/3a7a0b4a3bf589334d7816065377e8cbbd4e5cd9/docs/development/SKILLS_DEVELOPER_GUIDE.md).
3. Frappe skill libraries already provide routing, version/project inspection and development procedures. Two unchanged MIT reference files from LUBUS are included with their notice. They are a partial reference bundle, not a complete installed skills package or proof of workflow accuracy. [Repository at inspected revision](https://github.com/lubusIN/frappe-skills/tree/afd9ea13afe8f3312e0dc53bcb483acac4ddf9ed).
4. Generic repository-understanding products are competitors too. Google describes continuously refreshed documentation and source-linked answers in Code Wiki. Repowise advertises agent context, architecture and change-impact tools. The remaining hypothesis is deeper installation-aware Frappe workflow coverage. [Google announcement](https://developers.googleblog.com/introducing-code-wiki-accelerating-your-code-understanding/), [Repowise](https://repowise.dev/).
5. Current v16 source requirements matter more than old installation snippets: inspected Frappe v16 declares Python 3.14 and Node >=24. The fetched official Docker development guide contains older Node/Python/version examples, so its defaults must not be treated as a v16 lockfile. [Frappe Python manifest](https://github.com/frappe/frappe/blob/4515014c87ece6cb20ee91d2cfb121c5cbd1ff4a/pyproject.toml), [Node manifest](https://github.com/frappe/frappe/blob/4515014c87ece6cb20ee91d2cfb121c5cbd1ff4a/package.json), [Docker guide](https://github.com/frappe/frappe_docker/blob/main/docs/05-development/01-development.md).
6. Frappe Cloud is deployment infrastructure, not a persistent editable development directory. Its docs state that app copies are refreshed from GitHub on bench deployment and that developer-mode changes there do not persist. [Site configuration FAQ](https://docs.frappe.io/cloud/sites/site-config). The app also needs an explicit supported-Frappe range in `pyproject.toml`. [Compatibility configuration](https://docs.frappe.io/cloud/custom-apps/app-versioning/versioning).

## Reuse decisions

| Source | Decision for this foundation | What remains to verify |
|---|---|---|
| Frappe v16 app boilerplate | Reused literal official template constants for packaging/hooks/layout, with notice preserved | A real Bench install, migration and packaging build |
| Frappe / ERPNext / HRMS v16 code | Canonical evidence, with immutable source identity; three ERPNext/HRMS files included as test fixtures | Broader workflow coverage and exact customer deployment identity |
| LUBUS router and project-triage references | Fetched unchanged with MIT license and blob hashes | Review applicability and referenced material before any runtime use |
| Frappe Flow | Optional orchestration evaluation after live v16 foundation | Supported extension mechanism, version pin, dependency footprint, permissions and usage measurements |
| FAC | Optional MCP/tool/skill adapter using documented external-app hooks | Installed contract tests, current permission behavior and compatible release pin |
| Graph/vector services | Deferred; start with deterministic facts and lexical retrieval | An evaluation or scale problem large enough to justify the dependency |

No FAC or Flow business/runtime code has been copied into the app. License declarations are recorded from upstream sources; redistribution and the final release license must be assessed for the actual combination shipped. Keep each third-party notice with the material it covers.

## Exact v16 source baseline

| App | Inspected branch | Commit |
|---|---|---|
| Frappe | version-16 | `4515014c87ece6cb20ee91d2cfb121c5cbd1ff4a` |
| ERPNext | version-16 | `5af6561f5aa48104559692fb4fd82f2580e8d338` |
| HRMS | version-16 | `2478afc7a8f4959d500f6d17522853f0d244e38f` |

These commits were observed independently. This does not establish that this particular trio has passed an integrated bench test. They are research inputs, not a certified release combination. Keep the source lock distinct from the tested environment lock.

## Official app creation route

Frappe's documented route is `bench new-app frappe_knowledge` inside a bench, followed by installation on a site. The current `frappe/utils/boilerplate.py` v16 source was fetched and its literal templates were extracted using Python AST without importing or running the generator. This produced the package scaffold; it is **not** a claim that the Bench command ran here. [Tutorial](https://docs.frappe.io/framework/user/en/tutorial/create-an-app), [v16 generator](https://github.com/frappe/frappe/blob/4515014c87ece6cb20ee91d2cfb121c5cbd1ff4a/frappe/utils/boilerplate.py).

The generated package declares `frappe = ">=16.0.0,<17.0.0"` under `tool.bench.frappe-dependencies`, and keeps Frappe out of pip dependencies because Bench manages it from its repository. ERPNext and HRMS are optional indexed sources, not mandatory installed applications for a knowledge-only site.

## Cost and orchestration evidence

Anthropic's engineering report describes substantial extra token use in its multi-agent research workload. Its numbers do not predict this application's cost, but they refute the assumption that dividing knowledge into more agents inherently saves tokens. [Engineering report](https://www.anthropic.com/engineering/multi-agent-research-system).

Use one model first; retrieve targeted evidence and measure the full bill, including indexing, embeddings if introduced, refreshes, tool schemas, history, reasoning/output, retries and hosting. Compare cost per correctly completed task against an existing coding assistant that already has efficient file search and good Frappe skills.

## Useful open-source contributions to consider

- Publish a provider-neutral, versioned evidence/context schema with examples and a test corpus for cross-app retrieval.
- Contribute verified v16 applicability notes and source references to existing skill libraries instead of duplicating their entire content.
- Contribute a small knowledge-search/impact tool through FAC's external-app hooks, if installed contract tests confirm the interface.
- Share reproducible Frappe/ERPNext/HRMS cross-app failure cases and tests upstream where they reveal an actual bug.

These are proposed contributions. No issue, pull request, public repository or message has been submitted on the user's behalf.

## Remaining research gaps

- No head-to-head installed evaluation of Flow/FAC or commercial competitor quality.
- No verified customer demand, pricing or token savings.
- No full-source semantic graph or complete permission/configuration extraction.
- No authenticated ChatGPT Project/Codex Cloud/Frappe Cloud setup completed.
- No v16 bench integration or end-to-end UI verification in this workspace.

Further investigation should close these concrete gaps rather than broaden the product into every Frappe module at once.
