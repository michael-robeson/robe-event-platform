# Robe Event Platform

Robe Event Platform is a deployable, GCP-targeted reference architecture for
building event-driven services. It is an independent platform repository, not
an extension of any application repository.

## Purpose and scope

This repository documents and implements reusable platform patterns and
services for asynchronous integration. Mailflow, Robecruit, and future
products are external producers or consumers. Their business logic,
application-specific event contracts, and data models do not belong here.

The first executable increment is a local reference slice that publishes an
illustrative semantic event through the Pub/Sub emulator and persists a
consumer-owned projection in PostgreSQL 17. It does not provision cloud
resources, implement product integrations, or add CI/CD workflows.

## Architectural principles

- **Documentation first:** explain material architectural choices in an
  Architecture Decision Record (ADR) before implementing them.
- **Clear boundaries:** keep service code separate from infrastructure and
  keep product-specific behavior in its owning application.
- **Cloud-targeted, not cloud-assumed:** target GCP while recording service
  selections, security posture, and operational requirements as decisions.
- **Deployable and operable:** future implementations should document how
  they are configured, deployed, observed, and tested.
- **Small, explicit increments:** do not add speculative scaffolding or
  workflows before there is an agreed implementation to support.

## Repository navigation

- [AGENTS.md](AGENTS.md) — concise, durable guidance for coding agents.
- [docs/architecture/overview.md](docs/architecture/overview.md) — conceptual
  architecture, boundaries, and intended repository layout.
- [docs/decisions/](docs/decisions/) — ADR conventions and template.
- [.github/workflows/](.github/workflows/) — reserved for future CI/CD
  workflows; none are defined yet.

Future implementation areas are documented in the architecture overview.
They will be added when needed rather than created as empty directories.

## Local development

See [the first vertical-slice guide](docs/development/first-vertical-slice.md)
for local setup and end-to-end verification.
