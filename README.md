# Robe Event Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PR CI](https://github.com/robe-land/robe-platform-event/actions/workflows/ci.yml/badge.svg?event=pull_request)](https://github.com/robe-land/robe-platform-event/actions/workflows/ci.yml)
[![Declared Python requirement](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Frobe-land%2Frobe-platform-event%2Fdevelop%2F.github%2Fbadges%2Fpython.json)](pyproject.toml)
[![Top language](https://img.shields.io/github/languages/top/robe-land/robe-platform-event)](https://github.com/robe-land/robe-platform-event)
[![Language count](https://img.shields.io/github/languages/count/robe-land/robe-platform-event)](https://github.com/robe-land/robe-platform-event)
[![Last commit](https://img.shields.io/github/last-commit/robe-land/robe-platform-event/develop)](https://github.com/robe-land/robe-platform-event/commits/develop)

Robe Event Platform is evolving toward a composable, event-capable application
platform. Its current implementation is a local, GCP-targeted reference slice
for event-driven services. It is an independent platform repository, not an
extension of any application repository.

> Maintained by [Robe Land](https://github.com/robe-land).
>
> Original work is licensed under [LICENSE](LICENSE). Third-party
> materials retain their applicable licenses and copyright notices; see
> the notices accompanying those materials and the repository's
> third-party attribution index, where applicable.

## Purpose and scope

The long-term goal is reusable technical and business capabilities that
applications can compose through explicit boundaries, using events where
appropriate rather than for every interaction. Mailflow, Robecruit,
FamilyOfSix, and future products remain external integrations. Their
product-specific business logic, contracts, and data models do not belong
here. A shared business capability requires a separately reviewed need and
ownership boundary.

The first executable increment is a local reference slice that publishes an
illustrative semantic event through the Pub/Sub emulator and persists
independently owned item and audit projections in PostgreSQL 17. It does not
provision cloud resources or implement product integrations.

## Architectural foundation

Start with the [platform vision](docs/architecture/platform-vision.md),
[architectural principles](docs/architecture/principles.md), and
[conceptual capability model](docs/architecture/capability-model.md).
These approved foundation documents describe direction and reasoning, not
new runtime or deployment decisions. The
[architecture overview](docs/architecture/overview.md#architectural-guidance)
explains their relationship to accepted ADRs and implementable contracts.

## Repository navigation

- [AGENTS.md](AGENTS.md) — concise, durable guidance for coding agents.
- [docs/architecture/overview.md](docs/architecture/overview.md) — conceptual
  architecture, boundaries, and intended repository layout.
- [docs/decisions/](docs/decisions/) — ADR conventions and template.
- [.github/workflows/](.github/workflows/) — pull-request verification
  workflows; no deployment workflows are defined.

Future implementation areas are documented in the architecture overview.
They will be added when needed rather than created as empty directories.

## Local development

See [the first vertical-slice guide](docs/development/first-vertical-slice.md)
for local setup, end-to-end verification, and the optional read-only workbench.

The Python badge reports the declared requirement, not tested versions. The
PR CI badge reports a pull-request run, not necessarily the current
`develop` commit. Badge displays may be cached.
