# ADR-0003: Persistence Independence

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

[ADR-0001](0001-platform-and-deployment-strategy.md) establishes PostgreSQL
17 locally and Cloud SQL for PostgreSQL in GCP as the initial relational
database direction. [ADR-0002](0002-messaging-and-reliability.md) establishes
database-independent semantic events and independent consumer processing.
Producers and consumers need to evolve independently without event contracts
coupling producers to a consumer's storage model.

The same semantic event may be useful to multiple consumers with different
responsibilities and persistence needs. One consumer might use PostgreSQL
initially, while another could later use SQL Server or a document database.
The platform must define where persistence mapping belongs without assuming
that a generic central persistence capability is necessary or that every
service needs a physically separate database.

Meaningful alternatives include producer-defined SQL or storage operations,
direct database sharing between producers and consumers, a centralized
generic persistence service, and consumer-owned mappings. Database isolation
could also be physical per service or logical within a shared database or
instance. Event sourcing is another distinct architectural choice: it makes
a durable event history the source of truth, whereas event-driven integration
uses events to communicate and update independently owned consumer state.

## Decision

Accept the following persistence-independence principles:

- Event producers publish semantic events as defined in ADR-0002. They must
  not prescribe SQL statements, physical database schemas, document
  structures, or consumer-specific storage operations.
- Each consumer owns the mapping from a semantic event to its own persistence
  model and the persistence behavior needed for its responsibility. The same
  event may therefore be materialized differently by different consumers.
- Use PostgreSQL as the initial persistence technology where relational
  storage is appropriate. Consumer-owned mappings may use other persistence
  technologies, including SQL Server or document databases, when justified;
  this does not promise automatic portability between technologies.
- Multiple logical consumers may initially share a PostgreSQL database or
  instance, but shared physical infrastructure does not imply shared data
  ownership. Consumers must not directly modify data owned by another
  consumer. Define logical ownership and access boundaries and make them
  enforceable where practical. Do not require database-per-service or
  separate deployment units, and do not prohibit later physical isolation.
- Persistence remains a consumer capability. A centralized generic
  persistence service is not required by this architecture and should be
  introduced only if a separately reviewed shared need justifies it.

For consumers that persist event effects transactionally, use a local ACID
transaction to commit the consumer's state changes and deduplication outcome
together, consistent with ADR-0002. A consumer that does not require
transactional persistence is not required to create a database transaction.
Each consumer advances independently; there is no cross-consumer transaction
or guarantee that all projections reflect an event at the same time.
Consumers may therefore be eventually consistent with one another, but
eventual consistency does not guarantee convergence. If an event cannot be
processed or recovered, projections may remain incomplete or inconsistent.
Evaluate each consumer's completeness and correctness against its intended
projection semantics, not by assuming different databases contain identical
representations. Apply ADR-0002's per-consumer observability and
failure-management principles to identify processing gaps and support
recovery. Refer to its open implementation decisions for retry,
dead-letter, replay, and telemetry details rather than duplicating them here.

This is event-driven integration, not event sourcing. Pub/Sub is the delivery
transport; this architecture does not designate it as a permanent,
authoritative event store. Do not assume that all past events remain
available or that an arbitrary consumer projection can be rebuilt from
Pub/Sub. Rebuilding a projection requires a separately designed historical
source and recovery strategy, such as archival retention, a replay
capability, or an appropriate snapshot.

Treat persistence schema evolution, event-contract evolution, and projection
rebuilding as related but distinct concerns. Consumers own their persistence
schema and its evolution. Event producers evolve semantic contracts under
ADR-0002's compatibility principles; a contract change does not prescribe a
consumer's database migration. Rebuilding a projection additionally depends
on available historical input, compatible consumer logic, and a defined
replay or snapshot strategy.

## Consequences

Consumer-owned mappings let different services represent the same business
fact in storage suited to their own queries and responsibilities, without
requiring producers to know those representations. PostgreSQL provides the
initial relational option, while other technologies remain possible through
consumer-owned implementations. Supporting another database still requires
technology-specific persistence logic, operational support, and validation;
semantic events alone do not make persistence code portable.

Allowing logical consumers to share a PostgreSQL database or instance can
reduce initial operational overhead, but increases the importance of
enforceable ownership and access boundaries. Consumers writing another
consumer's data would couple their behavior and compromise independent
ownership, even when both use the same physical infrastructure. Physical
isolation may improve fault, security, or scaling boundaries, at additional
operational and cost overhead. This ADR does not prescribe the boundary or
mechanism.

Independent subscriptions and consumer-local transactions allow each
consumer to make progress or recover without coordinating a transaction
across other consumers. The resulting projections can lag, disagree, or
remain incomplete if processing or recovery fails. Completeness and
correctness are consumer-specific and depend on each projection's intended
semantics; identical representations or eventual convergence are not
guaranteed. Recovery uses ADR-0002's failure-management principles and,
where available, controlled replay or rebuild. Its guarantees depend on
separate retention, dead-letter, archive, and snapshot decisions. Pub/Sub
alone does not provide an indefinite history for arbitrary rebuilds.

A centralized generic persistence service could centralize common
capabilities, but would introduce a shared dependency, ownership boundary,
and potentially a lowest-common-denominator model across different
consumers. It could also reduce autonomy and become a scaling or failure
concentration point. Consumer-owned persistence avoids requiring that
centralization, while allowing a future shared service if a concrete need is
reviewed.

The following implementation choices remain open:

- Logical ownership boundaries within a shared database or instance,
  including the specific namespace, access, and practical enforcement
  mechanisms.
- Criteria for when a consumer should move from shared resources to physical
  database or instance isolation.
- Consumer-specific schema migration and compatibility practices.
- The persistence technology and data model appropriate to each consumer.
- Retention, archive, snapshot, and replay capabilities required for
  recovery or projection rebuilding.
- How consumers detect, assess, and recover incomplete or incorrect
  projections according to their intended semantics.
- Whether a concrete shared requirement warrants a centralized persistence
  capability.
