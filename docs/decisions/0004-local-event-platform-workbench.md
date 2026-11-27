# ADR-0004: Developer Workbench for Troubleshooting and Experiments

- **Status:** Accepted
- **Date:** 2026-11-21
- **Revised:** 2026-11-24 — establishes the developer-only Workbench vision and
  identifies dynamic local resource discovery as the immediate increment.
- **Revised:** 2026-11-27 — permits explicitly enabled local synthetic
  publication under the restrictions below; discovery remains read-only.

## Context

Developers need to inspect the local demonstration's independently owned
consumer records without introducing a participant in the event path.
Neither the publisher nor Pub/Sub provides a permanent publication history,
and consumer records alone do not prove delivery or acknowledgment.
ADRs [0002](0002-messaging-and-reliability.md) and
[0003](0003-persistence-independence.md) retain their reliability and
ownership boundaries.

The Workbench is intended as a developer-only troubleshooting and
experimentation capability, independent of application processing. Its future
vision may include message capture, consumer-processing visibility, event
correlation, GCP integration, and multi-tenancy. These possibilities do not
change the local-only boundary.

Alternatives include a centralized event store, consumer-specific inspection
endpoints, or direct developer database queries. A central store would add a
new persistence and delivery dependency; new consumer endpoints would couple
the demonstrations to the tool. Manual queries avoid an application but make
independent observations harder to inspect together.

## Decision

Provide a developer-only React/TypeScript Workbench backed by a FastAPI
development API. It is not a business application and normal application
publication, delivery, and processing do not depend on it. Small consumer-specific read adapters
translate existing records into a common observation representation.

Use a dedicated local PostgreSQL role with only the schema and table read
privileges needed for inspection; do not use consumer or administrator
credentials at runtime. The Workbench does not change consumer-owned records
or event contracts.

The discovery increment is dynamic discovery of topics and subscriptions
from the local Pub/Sub emulator. Discovery includes the relationship between
each subscription and its topic, using the relationship reported by the
emulator rather than inferring it from resource names. The Workbench checks
existing HTTP endpoints for liveness. Discovery remains local-only and
read-only.

The local developer composition may explicitly enable interactive synthetic
publication to an observed topic on the local Pub/Sub emulator. A developer
selects a service-owned template, inspects or edits its payload, and explicitly
requests one publication. The Workbench validates the resulting message
against the service-owned contract and retains its identity and correlation
fields. A broker acknowledgment means only acceptance, not delivery or
processing. Publication is disabled unless explicitly enabled, never targets
GCP, and must not become a dependency of application processing. The
Workbench does not consume, acknowledge, or modify broker messages or control
containers.

Distinguish observed records, records not observed, and unavailable or
unknown sources. Label health checks as liveness and record timestamps as
database values. Do not infer publication acceptance, delivery,
acknowledgment, global ordering, projection completeness, or eventual
convergence from these observations. Pagination is a best-effort view rather
than a historical event stream.

### Future capabilities and boundaries

The following dispositions apply under
[ADR-0005](0005-evolutionary-architecture-and-incremental-delivery.md):

- **Captured message inspection and consumer-processing visibility — defer.** Any
  future visibility must be grounded in an authoritative source and must not
  consume or acknowledge messages. Resource configuration, liveness, and
  persisted records alone do not prove processing outcomes.
- **Synthetic message publication — implement locally.** Explicitly enabled
  single-message experiments use service-owned contracts and templates; bulk
  publication and performance benchmarking remain deferred.
- **Event correlation — accommodate existing contracts only.** Use the
  identifiers defined by [ADR-0002](0002-messaging-and-reliability.md) where
  available; correlation is not proof of causation or successful processing.
  No new event contract or processing inference is introduced here.
- **GCP integration — defer.** The current Workbench is limited to the local
  emulator and local database. Remote access requires a separate decision
  addressing identity, authorization, least privilege, and environment
  boundaries, consistent with
  [ADR-0001](0001-platform-and-deployment-strategy.md).
- **Sensitive payloads — defer.** Developer-only access does not inherently
  authorize access to sensitive payloads. Before exposing them, a separate
  decision must establish explicit identity, authorization, and appropriately
  scoped access. Synthetic templates must not contain sensitive data.
- **Multi-tenancy and tenant data — defer.** The immediate increment does not
  introduce tenant access or isolation. Any future tenant-specific capability
  requires an explicit authorization model and appropriately scoped access
  and isolation; Workbench access alone does not grant it.

These are future considerations, not implementation requirements or
authorization to add speculative scaffolding. Security, correctness, and data
integrity required by the immediate increment remain in scope.

## Consequences

Developers can compare independently persisted local projections and
dynamically inspect local topic and subscription configuration without
changing the producer or consumers. The Workbench depends on the current
consumer schemas and needs explicit read grants and maintenance when those
schemas evolve. Its access is intentionally local and is not a production
observability design.

Missing or unavailable observations cannot diagnose why an event is absent.
The Pub/Sub emulator and local database do not demonstrate production
identity, delivery guarantees, or permanent event history. Richer telemetry,
remote access, sensitive-data access, and
historical recovery require separate review rather than being implied by this
decision.
