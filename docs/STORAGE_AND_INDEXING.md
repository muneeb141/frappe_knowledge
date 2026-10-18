# Storage and indexing decision for the v16 knowledge app

Reviewed 18 October 2026 after storing the full eligible local v16 source inventory. This is an indexing decision, not a claim that complete behavior knowledge or model integration has been tested. The installed site runs MariaDB 10.11.14. Reassess retrieval quality with held-out developer and support questions.

## Recommendation

Keep the Frappe/MariaDB records as the authoritative, versioned store for source identity, evidence and graph relationships. Keep canonical JSON as a versioned import/export and integrity format; do not make one large JSON blob the live query store. `FK Knowledge Row` now stores the full eligible three-app source inventory on the disposable site, but active-snapshot publication and production-scale validation remain open.

Use a staged retrieval pipeline: (1) authorize project and select exact snapshot/profile; (2) resolve exact DocType, symbol, path and alias identifiers; (3) retrieve ranked lexical candidates from source text/evidence and titles; (4) expand typed graph edges within budgets; (5) verify citations and surface missing coverage. Add semantic retrieval only when a held-out evaluation shows a recall gap. Neither a vector score nor an extracted link proves runtime behavior. Search indices are rebuildable projections of the authoritative records.

## Current implementation and scale risks

- `storage.py` writes file, node, edge, exact-title and title-term rows in batches of 500. Migrations create composite B-tree indices for snapshot/kind/lookup and edge endpoints. New snapshots omit the full graph field. The full local snapshot stored 281,306 rows in 183 seconds; row counts were checked. This is one direct worker-service run, not a queue/refresh benchmark.
- Exact normalized titles are resolved first. The term query then orders candidates by matched-term count in SQL before fetching up to 500. This removes the prior arbitrary hash-order cap, but the limit can still miss relevant graph seeds.
- A separate `FK Source Chunk` projection now stores 27,077 bounded excerpts derived from source files whose hashes match the snapshot. Its `search_text` splits snake_case/camelCase while `content` preserves the source. A custom InnoDB FULLTEXT index survived a second migration. The observed table footprint was about 139 MB data plus 20 MB indexes. SQL lexical candidates are reranked for path matches and implementation files, then diversified by source file. It covers indexed Python and DocType JSON only; MariaDB's token and stopword rules remain a recall limit.
- Relationship expansion uses a relevance-first traversal and prefers source relationships such as controller-module and DocType use. It has node/hop/character budgets and reads at most 10,000 adjacent edges per step. Benchmark high-degree nodes, cold and warm latency, database size, import duration and concurrent reads during refresh.
- The 20 MB HTTP import remains for bounded external snapshots. A local worker path builds directly from clean installed app checkouts without an HTTP payload. The pre-relationship scan of the three trees produced 6,314 eligible files, 40,570 nodes, 38,633 edges and a 75,040,602-byte canonical snapshot, with about 600 MB peak process memory. The latest stored graph has 39,623 edges; 124 dynamic links still require runtime resolution. Whole-snapshot construction is memory heavy. Add bounded chunking, deeper stored-row validation and atomic active-snapshot selection before routine refresh.
- Before adding chunks, single full-snapshot site reads took 1.23 seconds for Payroll Entry, 1.23 seconds for Journal Entry and 2.32 seconds for an exact Python function. Those are not p95 latency measurements. The [new retrieval check](RETRIEVAL_EVALUATION.md) found the expected file in the first five cited excerpts for 4/5 independent questions; it did not measure answer correctness.

## Options and their roles

| Option | Suitable role | Decision now |
|---|---|---|
| Canonical JSON | Portable, versioned snapshot exchange, content hashing and rollback | Keep; not the primary query engine |
| Frappe DocTypes + MariaDB B-tree rows | Authoritative identities, relationships, permissions, snapshot metadata, exact lookup and bounded graph traversal | Keep and benchmark |
| MariaDB 10.11 FULLTEXT | Ranked search over rebuildable source chunks | Implemented as a first lexical projection. Keep exact lookup; InnoDB token-length and stopword behavior means FULLTEXT cannot replace symbol/path search. The migration-created index survived schema sync locally. [MariaDB FULLTEXT documentation](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/optimization-and-indexes/full-text-indexes/full-text-index-overview) |
| LanceDB | Optional embedded full-text/vector search projection if evaluated retrieval improves and its filesystem/backup/worker deployment fits the host | Benchmark before adoption. Flow currently depends on LanceDB and LiteLLM, but that does not require this app to use its storage. [LanceDB search documentation](https://docs.lancedb.com/search), [Flow package at inspected revision](https://github.com/frappe/flow_client/blob/4a3189b6cbef0cad8ed16b24220d11242672996b/pyproject.toml) |
| External vector service | Optional when measured corpus, concurrency, filtering or operations exceed the embedded approach | Defer; adds deployment and authorization work. [Qdrant hybrid search documentation](https://qdrant.tech/documentation/tutorials-basics/cloud-inference-hybrid-search/) |
| MariaDB native vectors | Possible future deployment option | Not available in this site's MariaDB 10.11; MariaDB documents general availability in 11.8. Do not upgrade the Bench solely for this feature. [MariaDB Vector](https://mariadb.org/projects/mariadb-vector/) |

The next lexical comparison should test this FULLTEXT projection against code-aware postings/BM25 on a larger, independently written question set. Measure recall@k, citation correctness, truncation, p95 latency, import/refresh time, storage size and permission isolation. Only then test dense embeddings plus lexical fusion on natural-language misses; pin embedding model, dimensions and content hashes so the derived index can be rebuilt.

## Related open source and model integration

- [Frappe Assistant Core](https://github.com/buildswithpaul/Frappe_Assistant_Core) is relevant for authenticated MCP/tool access, audit and external-app integration. It is not the versioned source-evidence store. Evaluate its supported extension contract and permissions before connecting it; do not copy its runtime code into this app.
- [Frappe Flow](https://github.com/frappe/flow_client) is relevant for model/tool orchestration and has LiteLLM plus LanceDB dependencies at the inspected revision. Treat it as an optional consumer of the same authorized context API, not an owner of snapshot truth.
- [Frappe Skills](https://github.com/lubusIN/frappe-skills) provides procedural guidance. Skills and source evidence have different trust and update rules.
- [LiteLLM](https://docs.litellm.ai/docs/) is a model API/gateway layer with routing, retries and usage features. It is not a graph or knowledge database. Use it behind a provider-neutral `ModelAdapter` only if Phase 5 needs multi-provider routing or Flow already supplies it. Its optional vector-store routing does not make it the authoritative knowledge store.
- [LlamaIndex](https://developers.llamaindex.ai/python/framework/module_guides/storing/save_load/) is an indexing/retrieval framework with configurable document, index and vector stores. Its default in-memory/disk persistence is not a substitute for this app's installation identity, authorization and evidence schema. A local search prototype can compare it, but adopting it is not required to make storage future-proof.

## Adding more Frappe apps

Add each app through a registered source adapter and compatibility rule: app/repository identity, actual installed or declared revision, version scope, license, exclusions and content hashes. Extend the same extraction and retrieval contracts; do not create a separate knowledge database or model per app. A full source inventory must record parse failures and unsupported relationship types. Capture effective site metadata separately, because source files alone cannot establish Custom Fields, Property Setters, workflow settings or permissions on a particular site. Test cross-app edges and authorization before declaring an app supported. The present registry allows only Frappe, ERPNext and HRMS v16; support for another app is a deliberate code and evaluation change.

## Release gates

1. Finish Phase 1 clean-install verification on an authorized fresh site.
2. Expand held-out evaluation beyond the first five questions; measure the workflow miss, 500-title-candidate cap, FULLTEXT token misses, p95 latency and concurrent refresh behavior.
3. Choose the smallest search projection that meets recall, citation, latency and isolation targets; document its rebuild and migration path.
4. Add a single configured model through the neutral adapter only after retrieval is evaluated. Measure cost per correctly answered held-out task, including indexing and refresh.

No Flow, FAC, LiteLLM, LlamaIndex, LanceDB or vector database was installed or benchmarked in this research pass.
