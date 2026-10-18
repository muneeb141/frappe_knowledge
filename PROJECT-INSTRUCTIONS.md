# ChatGPT / Codex project instructions

Working name: Frappe Knowledge. Owner: Muneeb Mohammed. Objective: an installable Frappe app providing exact-version, cross-app source evidence and dependency context for AI-assisted support and development.

Implement **Frappe / ERPNext / HRMS v16** first. Start with payroll and accounting connections. Preserve the architecture boundaries in `docs/ARCHITECTURE.md`; use `docs/STATUS.md` as the current implementation record and `PLAN.md` for the next work. Keep a future v15 knowledge profile isolated and disabled until verified.

Reuse suitable maintained open-source components after checking actual compatibility, source, notice and installed behavior. Keep the knowledge domain independent of Flow/FAC or a model provider. Start with one model once the deterministic core and real bench integration are verified. No model provider or API credential decision has been made.

Prioritize correctness, evidence provenance, installation-specific customizations, permission enforcement and total cost per correctly completed task. Retain unresolved dependencies and knowledge gaps in answers. Capture candidate lessons automatically only when that feature is implemented; validate them before trusted reuse.

The indexed source store, sample import, restricted APIs, JSON Desk viewer and first field-level site overlay work on disposable local `ai.localhost`. The React dashboard, workflow/permission overlay and live model integration remain future phases. Follow `PLAN.md` for the next bounded implementation slice.

Project setup status: no ChatGPT Project, remote Git repository, Codex Cloud environment or Frappe Cloud site was created in the research session. The available ChatGPT browser was signed out, and no cloud provisioning account was accessible. Keep the source package and architecture available while account setup is completed.
