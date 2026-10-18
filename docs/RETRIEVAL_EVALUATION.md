# Source-text retrieval check

18 October 2026, disposable `ai.localhost`, snapshot `fe72602516f204104858e38509fa0a1e36a5d0c9ce3c2c8ed776ab780a1adcfc` (installed Frappe 16.52.0, ERPNext 16.51.1, HRMS 16.51.0). This evaluates whether a known implementation file appears among cited source excerpts; it does **not** score whether the excerpt answers the question correctly.

The local worker verified source-file hashes and stored **27,077 bounded chunks** for the existing snapshot. `FK Source Chunk` uses an InnoDB FULLTEXT index over a normalized search projection; exact symbol lookup still comes from graph/title rows. The table's observed `data_length` was 139,313,152 bytes and `index_length` was 20,135,936 bytes after indexing. InnoDB's reported table row estimate was lower than the exact 27,077 count, so it is not used as the count.

## Fixed question sets

The [development set](../tests/fixtures/retrieval-development-v16.json) was used while tuning ranking. Its first run found the expected file in the first five excerpts for 4/5 questions; after prioritizing implementation files and diversifying source paths, it found 5/5. This is a regression set, not an unbiased quality estimate.

The separate [held-out set](../tests/fixtures/retrieval-heldout-v16.json) was fixed before its first run. Expected files were initially in the first five excerpts for **4/5**, and first for **2/5**:

| Question topic | Expected file rank | Result |
|---|---:|---|
| Stock Entry valuation | 3 | Found |
| Frappe workflow transition validation | — | Missed `frappe/model/workflow.py`; workflow DocType files ranked instead |
| Expense Claim submission | 1 | Found |
| Payment Entry invoice allocation | 1 | Found |
| Frappe background job enqueue | 3 | Found |

On 19 October, the miss was traced to ranking rather than an absent chunk: `frappe/model/workflow.py` appeared fourth in the raw FULLTEXT results for the workflow question, but the later absolute DocType-path preference pushed it out of the excerpts. A new [six-question validation set](../tests/fixtures/retrieval-validation-v16.json) was fixed and run before changing ranking. Its baseline was **5/6** within five excerpts and **4/6** first; a differently worded workflow-state question missed the same file.

The ranker now keeps its existing path and DocType ordering, while giving location questions one second-position slot for a strong Python module outside DocType, patch and report directories. It only uses a module whose FULLTEXT relevance is at least 70% of the strongest candidate. This restored both workflow citations without discarding the existing DocType-focused results. On the same snapshot, after the change:

| Set | Before, expected file in first five | After, expected file in first five | After, first |
|---|---:|---:|---:|
| Development, 5 questions | 5/5 | 5/5 | 3/5 |
| Earlier held-out, 5 questions | 4/5 | 5/5 | 2/5 |
| New validation, 6 questions | 5/6 | 6/6 | 4/6 |

All 16 responses stayed within the 16,000-character context budget. The two workflow excerpts pointed to `frappe/model/workflow.py` at lines 271–315 and 226–270, respectively; their returned text matched the cited lines in the pinned local checkout. The first excerpt contains the transition check body but not the function declaration. These are regression results after inspection and tuning, **not** an untouched quality estimate or a judgment that every excerpt answers its question correctly. Reproduce any set with `bench --site ai.localhost execute frappe_knowledge.evaluation.run_suite --kwargs '{"snapshot":"fe72602516f204104858e38509fa0a1e36a5d0c9ce3c2c8ed776ab780a1adcfc","suite":"validation"}'`, replacing `validation` with `development` or `heldout` as needed. It makes no model or web request.

## Limits and next comparison

MariaDB FULLTEXT ignores configured stopwords and short tokens; this site's index uses the server defaults. Natural-language search can miss code when the user's wording differs from names in the source. The current ranker is lexical, uses a capped candidate pool, and returns bounded source chunks with file/line/commit citations. The workflow miss is addressed in these regression sets, but a larger untouched question set with relevance and citation judgments is still needed. Measure cold/warm p95 and concurrent project filtering, and compare with a code-aware postings/BM25 alternative before adding embeddings. A retrieved chunk is source text, not tested runtime behavior.

Hard character budgets can omit a large graph node. On this full snapshot, the exact `get_advance_deductions` query returned a cited source excerpt at 4,000 characters and both the symbol node and an excerpt at 6,000; 2,000–3,000 characters were too small for either payload. The default 16,000-character budget retained both. This is a visible coverage limit, not a token guarantee.

[MariaDB FULLTEXT behavior](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/optimization-and-indexes/full-text-indexes/full-text-index-overview) documents its token and stopword constraints.
