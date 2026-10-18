# ADR 0002: React dashboard and separate version boundaries

Date: 18 October 2026. Status: accepted by the supplied local implementation brief.

Use a same-origin React + TypeScript + Vite dashboard at `/knowledge`, with Frappe Desk retained for administration and the starter JSON viewer as a fallback. The dashboard will use Frappe sessions/CSRF and a typed API client; it will not add another authentication database or put model secrets in browser assets.

Keep host runtime compatibility separate from knowledge-profile compatibility and each indexed app's own version. Implement only the v16 host and `frappe-v16` knowledge profile now. A future v15 knowledge profile is disabled until its source rules and tests exist; a v15 host port is an independent effort.

This replaces the earlier assumption that the standard Desk page is the final product UI and that every source app must have a version string beginning with `16`. Storage and React contracts will be versioned as Phase 2 and Phase 3 are implemented.
