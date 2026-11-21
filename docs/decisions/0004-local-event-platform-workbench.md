# ADR-0004: Local Event Platform Workbench

- **Status:** Accepted
- **Date:** 2026-11-21

## Context

Developers need to inspect the local demonstration's independently owned
consumer records without introducing a participant in the event path.
Neither the publisher nor Pub/Sub provides a permanent publication history,
and consumer records alone do not prove delivery or acknowledgment.
ADRs [0002](0002-messaging-and-reliability.md) and
[0003](0003-persistence-independence.md) retain their reliability and
ownership boundaries.

Alternatives include a centralized event store, consumer-specific inspection
endpoints, or direct developer database queries. A central store would add a
new persistence and delivery dependency; new consumer endpoints would couple
the demonstrations to the tool. Manual queries avoid an application but make
independent observations harder to inspect together.

## Decision

Provide a local-only, read-only React/TypeScript workbench backed by a FastAPI
development API. It is not a business application and does not participate in
publication, delivery, or processing. Small consumer-specific read adapters
translate existing records into a common observation representation.

Use a dedicated local PostgreSQL role with only the schema and table read
privileges needed for inspection; do not use consumer or administrator
credentials at runtime. The workbench does not change consumer-owned records
or event contracts. Query the local emulator only for existing topic and
subscription configuration, and check existing HTTP endpoints for liveness.
Do not consume messages or control containers.

Distinguish observed records, absent records, and unavailable sources.
Label health checks as liveness and record timestamps as database values.
Do not infer publication acceptance, delivery, acknowledgment, global
ordering, projection completeness, or eventual convergence from these
observations. Pagination is a best-effort view rather than a historical
event stream. The tool exposes no experiment or fault-injection controls in
this increment.

## Consequences

Developers can compare the independently persisted local projections without
changing the producer or consumers. The workbench depends on the current
consumer schemas and needs explicit read grants and maintenance when those
schemas evolve. Its access is intentionally local and is not a production
observability design.

Missing or unavailable observations cannot diagnose why an event is absent.
The Pub/Sub emulator and local database do not demonstrate production
identity, delivery guarantees, or permanent event history. Future experiment
controls, richer telemetry, remote access, and historical recovery require
separate review rather than being implied by this decision.
