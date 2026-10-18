# Frontend direction

The approved product dashboard is a React + TypeScript + Vite SPA in this app, served at `/knowledge` on the Frappe origin. Phase 3 will implement the first real vertical slice. The currently installed `/desk/frappe-knowledge` page is a JSON context viewer and administrative fallback; it is not the React dashboard. Its **Index installed sources** button queues a local scan for a System Manager. The UI currently reports only the queued job ID, not progress or completion.

Use Frappe's existing session and CSRF protection. Keep provider credentials on the server. Before selecting an SDK, inspect the current primary `frappe-react-sdk` source, peer dependencies and actual v16 behavior; keep network calls behind a typed client. Doppio is an optional scaffold reference. The development proxy, production asset paths and deep-route fallback must be verified against this Bench (web port 8005), then pinned in a single frontend lockfile.

The first screen should select the authorized project/profile/snapshot, ask for bounded context, and display source evidence with coverage and unknowns. Loading, empty, denied and failure states must use real API outcomes. Render source strings as text. Do not expose unfinished model, sync, lesson or usage actions as functioning controls.
