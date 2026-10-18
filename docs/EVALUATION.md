# Evaluation design and results

No model quality or cost benchmark has run. The current partial fixture confirms a static payroll-to-Journal-Entry extraction path; it does not establish complete payroll workflow understanding or token savings.

Prepare about 30 representative cases and a held-out set using the exact source revisions and effective site configuration. Cover payroll accrual and cancellation, component/account settings, cross-app changes, customizations, wrong-version traps, unsupported questions, authorization failures and source changes. Each case needs expected evidence and workflow facts, not only a final prose answer.

Compare a capable coding assistant with direct repository access and Frappe skills against the same assistant supplied with this context service. Hold model and available tools constant where possible. Measure correctness, missed dependencies, wrong-version recommendations, unsupported claims, rework/regressions, latency and total cost per correctly completed task. Report initialization, update and hosting costs separately. Record measured usage only; mark estimates and unknowns.

## Current verification

- 19 offline core tests passed on Bench Python 3.14.7.
- Four site integration tests passed after migration on `ai.localhost`.
- No held-out task set, live model calls or cost measurements yet.
