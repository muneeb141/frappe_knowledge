# Host and knowledge versioning

The app currently runs on a Frappe v16 host. `pyproject.toml` declares Frappe `>=16.0.0,<17.0.0`; this describes **where the app runs**, not which source versions it can discuss.

The active knowledge profile is `frappe-v16`. `core/profiles.py` is its source-app and compatibility registry: it allows the three known repositories at their v16 app versions. A supported custom app can be added there with its own repository and major version, which need not be 16. The host runtime range remains in `pyproject.toml` and is independent of these indexed source versions.

New snapshots use schema 3 and carry `profile_id` plus optional, source-authored descriptions with their own evidence locations. The selected profile is also stored on `FK Project` and `FK Snapshot`. Import and retrieval check all three identities and validate the declared source set against the registry. A snapshot pins each source to a full Git SHA; the profile registry does not replace that per-snapshot identity. Existing schema-2 snapshots remain readable; old schema-1 snapshots are interpreted as `frappe-v16` only and were backfilled on `ai.localhost` without changing their original snapshot IDs. Context packages retain their own schema 1 and now include a deterministic relation glossary.

Future v15 knowledge remains unavailable until its rules, fixtures, storage isolation, retrieval checks and evaluations exist. It may eventually be served from a v16 host. Running this app on a v15 host is a separate runtime port and must not be inferred from the knowledge profile.

Snapshot identity alone proves payload integrity, not a claimed checkout revision. The offline CLI verifies clean Git roots for normal indexing; the included fixture explicitly marks checkout verification false. Local dirty customizations require a separate provenance overlay or an approved clean baseline and must never be reset to satisfy indexing.

`FK Source Chunk` is a rebuildable text-search projection attached to a snapshot; it does not change the schema-3 snapshot hash. Local indexing checks every source file against that snapshot's file hash before storing chunks. Older and bounded HTTP-imported snapshots remain readable without chunks; they return no source-text matches until an authorized matching local checkout is indexed.
