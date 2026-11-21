# ADR-0002: Messaging and Reliability

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

[ADR-0001](0001-platform-and-deployment-strategy.md) establishes the platform's
messaging and execution direction. Independently deployed producers and
consumers need a shared event meaning and clear reliability boundaries
without sharing database schemas or requiring synchronized releases.

The event model should describe business facts, not SQL statements, physical
database rows, or a representation tailored to one consumer. A topic can
serve multiple independent consumers; each consumer that must process the
event independently needs its own subscription. Sharing a subscription
between instances of one logical consumer distributes work among them rather
than broadcasting a copy to each instance.

Meaningful alternatives include synchronous point-to-point calls, raw
database-change messages, consumer-specific payloads, and a shared
consumer-group subscription. Reliability alternatives include attempting
exactly-once processing or a distributed transaction across the producer,
broker, and consumer database, versus at-least-once delivery with local
transactions and idempotent consumers. Ordering can be required globally or
per key, or omitted where consumers can process events independently.

## Decision

Establish a semantic event envelope with these required logical elements.
They describe the event meaning, not a wire schema or a database schema:

- **Event identity (`event_id`):** identifies one logical event and remains
  unchanged across publication retries and message redelivery.
- **Event type (`event_type`):** names the business fact independently of
  the producer's implementation and consumers' processing needs.
- **Contract version (`contract_version`):** identifies the version of the
  public meaning and payload contract for that event type.
- **Occurrence time (`occurred_at`):** records when the event occurred, not
  when it was published or delivered.
- **Source (`source`):** identifies the producing application or service.
- **Payload (`payload`):** contains the domain facts consumers need, without
  embedding SQL, physical row representations, or consumer-specific
  projections.

Correlation (`correlation_id`) and causation (`causation_id`) identifiers are
optional logical elements. Correlation relates events within a broader
workflow; causation identifies the event or action that directly caused this
event. Wire serialization and identifier formats are not defined here.

Use independent Pub/Sub subscriptions for independently processing logical
consumers. Treat each subscription's delivery and processing outcome
separately; successful handling by one consumer does not establish handling
by another.

Treat publication acceptance, delivery, and processing as distinct outcomes:

- A successful publish response means Pub/Sub accepted the message for
  delivery under its service and retention guarantees; it does not mean that
  any consumer has processed it.
- A successful push response acknowledges that message for that
  subscription only. Return a Pub/Sub-recognized success response only after
  the consumer's required durable processing has completed. For consumers
  that persist state transactionally, commit the state changes and
  deduplication record together before responding successfully. Consumers
  that do not require transactional persistence are not required to create a
  database transaction. For push delivery, Pub/Sub currently recognizes HTTP
  statuses `102`, `200`, `201`, `202`, and `204` as success; other statuses
  are negative acknowledgments.
- A timeout, connection failure, negative acknowledgment, or expired
  acknowledgment deadline can result in redelivery. This includes the case
  where the consumer committed its transaction but the response was lost.

Pub/Sub push acknowledgments are governed by a configured acknowledgment
deadline; unlike pull delivery, a push consumer cannot extend the deadline
for an individual message. The current supported deadline range is 10 to
600 seconds. The Cloud Run request timeout is a separate limit. Synchronous
processing must be designed and configured to finish within both limits;
otherwise Pub/Sub can redeliver while a request is still running. Exact
deadline, request-timeout, and processing-time targets remain open. A
consumer must not acknowledge early merely to avoid those limits.

Use at-least-once delivery and require consumers to tolerate duplicates.
Consumers must use the stable event identity to make repeated delivery safe.
For consumers that persist state transactionally, commit the deduplication
record and state changes in the same local transaction. Other consumers must
use an idempotent operation or another suitable mechanism for duplicate-safe
processing. Effects in another system need their own idempotency or durable
coordination; a local database transaction cannot make those effects atomic.

Do not require a distributed transaction spanning a producer's database,
Pub/Sub, and a consumer's database. Producers publish events, Pub/Sub accepts
and delivers them, and consumers complete their own required durable
processing. When a producer must atomically couple a local state change with
publication intent, it must use a transactional outbox or an equivalent
reliable publication mechanism. An outbox is not required for every
publisher. This producer-side mechanism avoids requiring a distributed
transaction; its implementation is left open.

Assume no global or per-key ordering unless a use case explicitly requires
it. Event occurrence timestamps do not establish a total order. Pub/Sub
ordering requires publisher ordering keys and subscription ordering
configuration, and has regional and redelivery implications. Whether to use
ordering, the relevant key, and the ordering scope remain open.

For transient processing failures, return a negative acknowledgment or allow
the request to time out so Pub/Sub can retry. Treat permanently
unprocessable events, such as those that fail permanent contract or
validation checks, as poison messages rather than as transient failures.
Use bounded retries and a dead-letter topic to isolate messages that remain
unprocessable, rather than silently acknowledging them or retrying without
end. Pub/Sub dead-letter forwarding occurs after a configured, best-effort
number of delivery attempts; it does not itself classify a failure as
transient or permanent. Dead-lettering is an operational isolation
mechanism, not proof of successful business processing. Messages sent there
require visibility, diagnosis, controlled remediation, and a replay path.

Favor backward-compatible, additive event-contract evolution so independently
deployed consumers can adopt changes without a lockstep release. Treat
incompatible changes to event meaning or payload as a new contract version.
For a version transition, consumers should be prepared for supported versions
before producers emit the new version, and old-version support should remain
through the transition and relevant subscription backlog or replay window.
The exact wire encoding, payload-field requirements, versioning scheme,
compatibility rules, and transition process are not defined by this ADR.

Instrument publication acceptance separately from processing outcomes for
each subscription. Consumer telemetry should make it possible to correlate
processing by event identity, type, source, and correlation identifier, and
to observe processing latency, acknowledgment failures, redeliveries,
subscription backlog or message age, and dead-letter volume. Avoid logging
payload contents by default. Exact metrics, alert thresholds, tracing
propagation, and sensitive-data controls remain open.

## Consequences

The semantic envelope gives independently deployed consumers stable
information for routing, deduplication, tracing, and contract interpretation
without coupling them to a producer's SQL or physical schema. Separate
subscriptions provide independent progress and failure handling, at the cost
of additional delivery, retention, and operational management for each
consumer.

At-least-once delivery with consumer-local durable processing avoids the
coordination and availability costs of a distributed transaction, but makes
duplicate-safe consumer behavior essential. For transactional persistence
consumers, a committed transaction followed by a lost acknowledgment can be
processed again, so the state change and deduplication record must commit
together. Durable acceptance by Pub/Sub also does not make the producer's
local state update and publication atomic; producers that require that
atomicity must use an outbox or equivalent reliable mechanism.

Push delivery provides a straightforward HTTP integration with Cloud Run, but
the acknowledgment deadline and request timeout constrain synchronous work.
Retrying can increase latency and load, while dead-letter handling and replay
add operational responsibilities. Ordering can reduce concurrency and
increase latency, and redelivery can affect later messages with the same
ordering key; enable it only for a reviewed requirement.

Backward-compatible contracts support independent deployment, but consumers
and producers may need to support multiple versions during a transition.
Uncoordinated incompatible changes risk breaking lagging consumers.

The following implementation details remain open for subsequent review and
decisions:

- Envelope serialization, identifier formats and uniqueness scope, and
  timestamp format.
- Topic and subscription ownership, naming, filters, retention, and replay
  practices.
- The specific producer-side outbox or equivalent mechanism and the
  criteria for when atomic publication intent is required.
- Consumer idempotency storage, retention period, and handling of external
  side effects.
- Whether any event types require ordering, and their key and scope.
- Retry backoff, maximum delivery attempts, acknowledgment-deadline and
  Cloud Run timeout values, and processing-time objectives.
- How to distinguish and disposition permanently unprocessable events before
  the configured dead-letter attempt threshold.
- Dead-letter topic ownership, forwarding configuration, monitoring, access,
  retention, remediation, and replay procedures. Pub/Sub dead-letter
  forwarding is best effort, so the policy must account for that limitation.
- Contract compatibility rules, version format and scope, transition
  support window, and retirement criteria.
- Detailed per-consumer metrics, alert thresholds, tracing propagation, and
  controls for sensitive data in event payloads and telemetry.

Google documents the current [push response and acknowledgment
behavior](https://cloud.google.com/pubsub/docs/push),
[subscription acknowledgment deadlines and retry
settings](https://cloud.google.com/pubsub/docs/subscription-properties), and
[ordering behavior](https://cloud.google.com/pubsub/docs/ordering). Their
service-specific details should be revalidated when implementation choices
are made.
