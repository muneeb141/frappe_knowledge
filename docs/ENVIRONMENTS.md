# Development and cloud setup

Scope: v16 host and active `frappe-v16` knowledge profile. The local Bench verification below is current; cloud sections remain prepared guidance. Actual implementation state is recorded in STATUS.md.

## Verified local Bench

The development Bench is `/home/muneeb_mohd/frappe/ai`; the disposable site is `ai.localhost`, with MariaDB and Frappe, ERPNext, HRMS and `frappe_knowledge` installed. Bench Python is 3.14.7, Node is 24.21.0, Yarn is 1.22.22, Bench is 5.31.0, Redis is 7.0.15 and MariaDB is 10.11.14. `Procfile` serves web on port 8005 and socket.io on port 9005. This site has `developer_mode` and `allow_tests` enabled for local verification. No credentials belong in this document.

The source revisions are recorded in `PLAN.md` and `sources.lock.json`. The app has a configured GitHub `origin`, but this work has not been committed or pushed. The starter source was merged into the existing app, then these commands succeeded:

```bash
cd /home/muneeb_mohd/frappe/ai/apps/frappe_knowledge
/home/muneeb_mohd/frappe/ai/env/bin/python -m unittest discover -s tests -v
/home/muneeb_mohd/frappe/ai/env/bin/python -m frappe_knowledge.cli index tests/fixtures/manifest-v16.json --fixture --output build/sample-snapshot.json
cd /home/muneeb_mohd/frappe/ai
bench --site ai.localhost migrate
bench build --app frappe_knowledge
bench --site ai.localhost run-tests --module frappe_knowledge.tests.test_api
```

The sample project `v16-research` and its imported snapshot exist on `ai.localhost`. The Desk fallback is at `http://ai.localhost:8005/desk/frappe-knowledge`. Authenticated retrieval, Guest denial, CSRF behavior and text-safe result rendering were checked. The React `/knowledge` route is planned, not yet built.

## Three different project/cloud concepts

| Surface | Purpose | Current state |
|---|---|---|
| ChatGPT Project | Keep research, instructions and project chats together | Not created; the available browser shows a signed-out ChatGPT session |
| Codex Cloud environment | Reusable remote development dependencies and authorized repository access | Not created/published; account/environment controls were not available through a connected tool |
| Frappe Cloud site/bench | Deploy and operate the Frappe app for staging/pilot | Not provisioned; no authenticated Frappe Cloud account/bench was available |

The connected GitHub app could read upstream code, but it exposes no repository-creation operation in this session. No new remote repository was created and no code was pushed. This source package is saved as a deliverable so development can continue without cloud provisioning.

Official references: [ChatGPT Projects](https://help.openai.com/en/articles/10169521-projects-in-chatgpt), [Codex Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments), [Frappe Cloud custom apps](https://docs.frappe.io/cloud/benches/custom-app).

## Required development runtime

The inspected Frappe v16 source declares Python `>=3.14,<3.15` and Node `>=24`. This app uses the v16 generator's Python floor and declares Frappe `>=16.0.0,<17.0.0`. Confirm exact patch/system dependency choices against the source revision you install. A compatible MariaDB/database setup, Redis, Bench and frontend build tools are also required.

Use a disposable Frappe development bench or a correctly configured official Frappe Docker development environment. The fetched Docker guide includes legacy-version examples; do not assume its example Node/Python defaults meet the current v16 source requirements.

## Existing-bench route

First run `python scripts/check_environment.py` from this project for a dependency preflight. Inside an already prepared v16 bench, import this source directory:

```bash
bench get-app /absolute/path/to/frappe_knowledge
bench new-site knowledge.localhost
bench --site knowledge.localhost install-app frappe_knowledge
bench --site knowledge.localhost set-config developer_mode 1
bench --site knowledge.localhost migrate
bench build --app frappe_knowledge
bench start
```

`bench new-site` prompts for database/admin credentials; do not put credentials into committed scripts. If the site already exists, skip creation. ERPNext/HRMS installation is only needed for the later runtime integration cases, not for indexing the provided downloaded source sample.

Before first install, initialize/commit the extracted package as a local Git repository if Bench's local `get-app` path requires it in your installed Bench version. Once a remote repository exists, use its real URL and a selected branch instead. Do not substitute an invented repository URL.

## Import the example

Generate the sample from this project root:

```bash
python -m frappe_knowledge.cli index tests/fixtures/manifest-v16.json --fixture --output build/sample-snapshot.json
```

On the development site, create an `FK Project` with Project Key `v16-research`, Title `v16 research`, and Framework Major `16`. In the authorized Bench console:

```python
import json
from pathlib import Path
from frappe_knowledge.api import import_snapshot
payload = json.loads(Path('/absolute/path/to/frappe_knowledge/build/sample-snapshot.json').read_text())
snapshot_name = import_snapshot('v16-research', payload)
frappe.db.commit()
```

Then open `/desk/frappe-knowledge`, choose the project/snapshot, and search `Payroll Entry`. The first UI displays a JSON context package; a chat/model-selection dashboard is a later milestone.

## Real source indexing

Create a manifest with one entry per approved clean repository checkout and a full commit SHA. Paths are resolved relative to that manifest. Use version `16` for each source. Omit `--fixture` to verify Git HEAD and a clean checkout before parsing. Checkouts must be repository roots, not subdirectories. Include only approved source trees; do not point an HTTP request at arbitrary server paths.

The provided fixtures are three files, not the full ERPNext/HRMS repositories. Their sample proves one extraction path, not comprehensive payroll understanding.

## Codex Cloud preparation

After an authorized Git repository exists and cloud controls are accessible:

1. Create a private development environment and add that repository using the account's supported connection flow.
2. Prepare the required Python/Node versions, database/queues and Bench, or connect an approved development environment that already supplies them.
3. Permit the source/package destinations actually needed for setup through the environment's network settings. Keep credential/configuration decisions explicit.
4. Run core tests, then the full Bench installation and authorization checklist below.
5. Save/publish the reusable environment only after its setup succeeds. Commit work to source control; do not rely on a cloud task's temporary files as the project backup.

No paid cloud plan, model API credentials, public endpoint or application-hosting subscription has been created by this package.

## Frappe Cloud staging preparation

Use a compatible v16 bench with the actual custom-app capability/account plan. Add the real Git repository and selected branch; verify `tool.bench.frappe-dependencies` during build. Deploy to a disposable staging site, install the app, migrate, and verify the same checks before a pilot.

Frappe Cloud app directories are ephemeral copies from source control. Do not use cloud developer-mode edits as the authoritative application source. Indexing may need a separate development worker and source/profile exchange rather than assuming Git is available in the hosted site's process.

## Required integration verification

- Clean install, migration, asset build, uninstall behavior and repeat installation.
- Project creation, valid sample import, repeat import and immutable-snapshot enforcement.
- Reject non-admin API calls and verify both project and snapshot access before reading context.
- Reject cross-project imports/context, incorrect revision data, oversized inputs and unsupported source majors.
- Render source strings containing HTML/script as plain text.
- Verify source URLs/line ranges and partial/truncation indicators in the actual UI.
- Repeat against the selected full Frappe/ERPNext/HRMS v16 environment and record exact commits.

The sample import, duplicate import, immutable save/delete, Guest denial, CSRF behavior, source links/truncation and text-safe browser rendering have been checked on `ai.localhost`. A separate Frappe-only site on an isolated local MariaDB server passed fresh install, migration, uninstall/reinstall and 7 integration tests; the asset build and 27 offline tests passed too. Full-corpus source indexing remains verified on `ai.localhost`, not on the fresh site. See `PLAN.md` and `STATUS.md` for the current gate.
