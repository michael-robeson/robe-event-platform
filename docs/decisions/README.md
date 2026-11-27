# Architecture Decision Records

Record significant architectural choices here so that implementation and
infrastructure have an explicit, reviewable rationale.

## Format

Create one Markdown file per decision, named
`NNNN-short-title.md` (for example, `0001-event-transport.md`). Use the
[ADR template](0000-template.md) and keep the record focused on one decision.

Each ADR includes:

- **Status** — proposed, accepted, superseded, or deprecated.
- **Date** — date the record was created or the decision was made.
- **Context** — problem, constraints, and relevant alternatives.
- **Decision** — the selected direction, or the proposal under review.
- **Consequences** — important trade-offs and follow-up work.

Accepted decisions:

- [0001](0001-platform-and-deployment-strategy.md) — platform and deployment
  strategy.
- [0002](0002-messaging-and-reliability.md) — messaging and reliability.
- [0003](0003-persistence-independence.md) — persistence independence.
- [0004](0004-local-event-platform-workbench.md) — local Workbench boundaries.
- [0005](0005-evolutionary-architecture-and-incremental-delivery.md) —
  evolutionary architecture and incremental delivery.
- [0006](0006-service-oriented-workbench.md) — service-oriented Workbench and
  descriptor contract.

Do not silently rewrite an accepted decision. Create a new ADR that explains
what it supersedes and why.
