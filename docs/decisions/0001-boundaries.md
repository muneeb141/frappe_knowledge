# ADR 0001 — modular v16 app with an independent knowledge core

Status: accepted for the research foundation, subject to measured pilot findings.

Context: existing Flow/FAC/skills projects cover orchestration and knowledge delivery, while the proposed value is exact-installation, cross-app evidence. The user selected v16 only.

Decision: build a Frappe control/permission adapter over a deterministic Python core; use immutable versioned knowledge snapshots and bounded retrieval. Keep model, storage and orchestration integrations replaceable. Start with one model and a narrow payroll/accounting workflow after the offline and bench foundations are verified.

Alternatives considered: a mandatory Flow/FAC fork; an agent for every feature; a generic chatbot; an external graph/vector stack from day one. Each either duplicates established capability or couples the unproven knowledge product to a larger dependency surface.

Consequences: more domain work remains ours, but model/runtime choices do not dictate knowledge identity. The sample JSON snapshot store must be replaced behind a repository boundary before broad scale. Knowledge updates and application upgrades are separate operations. No claim of complete static dependency inference or future architecture immutability is made.
