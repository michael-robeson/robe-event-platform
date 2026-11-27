# Local Service Topology Workbench

**Status:** Accepted for implementation

**Capability owner:** robe-platform-event Workbench

**Intended users:** Developers using the local Workbench

## Purpose and boundaries

Provide a service-oriented local Workbench whose primary view is an
interactive topology of infrastructure, independently maintained services,
topics, subscriptions, and their relationships. Developers can inspect
declared service identity and messaging, observed health, and runtime
configuration without joining the event-processing path.

The Workbench remains local-only and read-only. It does not publish, pull,
acknowledge, create, update, or delete Pub/Sub resources, write consumer data,
or connect to GCP. The existing demonstration status, inventory, consumer
observations, and event inspection remain available in a separate reference
view.

Synthetic publication, message inspection, consumer-processing visibility,
correlation tracking, performance benchmarking, remote access,
multi-tenancy, and sensitive payload access are outside this increment.

## Context and authoritative sources

- [ADR-0006](../decisions/0006-service-oriented-workbench.md) defines the
  approved descriptor and topology approach, primary UI, and deferrals.
- The [descriptor schema](../contracts/workbench-service-descriptor.v1.schema.json)
  is authoritative for the version 1 service interface.
- [ADR-0004](../decisions/0004-local-event-platform-workbench.md) continues to
  define the Workbench's read-only boundary and observation limits.
- [ADR-0005](../decisions/0005-evolutionary-architecture-and-incremental-delivery.md)
  distinguishes implementation needs from deferred capabilities.
- [ADR-0002](../decisions/0002-messaging-and-reliability.md) remains
  authoritative for messaging semantics; topology does not amend them.
- The [first vertical-slice guide](../development/first-vertical-slice.md)
  describes local composition and functional review.

## Requirements

1. A service may expose its identity, health path, and declared Pub/Sub
   topics, topic roles, subscriptions, delivery mode, and push endpoint using
   the platform-owned version 1 descriptor. The Workbench obtains descriptors
   only from explicitly configured HTTP origins; it does not scan networks
   or add service-specific adapters.
2. The topology shows the local Pub/Sub emulator, configured services, and
   all runtime-discovered topics and subscriptions. Discovery includes
   broker-reported subscription-to-topic relationships, even when the topic
   is absent from the topic inventory. Runtime configuration includes
   available subscription delivery and retry/dead-letter settings.
3. The UI distinguishes declared relationships from observed resource
   relationships. Service-to-topic roles are declarations; subscription-to-
   topic and subscription push-endpoint relationships are observations when
   confirmed by the emulator. A declared resource that is missing or
   mismatched remains visible and is not presented as observed.
4. Health is checked separately at the declared local relative endpoint and
   shown as an observed liveness result. It does not establish publication,
   delivery, acknowledgment, or processing.
5. Available empty inventories, partial results, missing declared resources,
   and unavailable sources remain distinct. A failure for one service or
   resource kind must not hide unrelated services, resources, or the
   demonstration diagnostics.
6. The interactive topology is the default view. Selecting a node exposes its
   identity, evidence source, health, and available configuration. Existing
   demonstration diagnostics and event inspection are available separately
   and do not load as part of the normal topology view.
7. Refresh obtains a new descriptor, health, and resource snapshot without
   restarting the Workbench. Discovery performs only read operations and
   does not access message payloads or modify service, broker, or database
   state.
8. The primary graph arranges relationships in the direction of message
   flow rather than fixed resource-type columns. It supports fan-out,
   dead-letter branches, and services that both consume and publish.
   Infrastructure containment is shown separately from message-flow edges.
   Labels and details remain legible across supported viewport sizes and
   light and dark themes.
9. A direct consumption shortcut may be suppressed when the same declared
   topic-to-subscription-to-service path is shown; the original declaration
   remains inspectable. A broker-reported dead-letter policy connects its
   subscription to the configured topic and does not assert forwarding
   occurred or that a service published the dead letter.

## Acceptance evidence

- The running Gmail service appears with the declared identity and health
  endpoint; its request, output, and dead-letter topics and subscriptions
  are represented without Workbench-specific Gmail logic.
- The local emulator's actual resources and reported relationships appear
  after refresh. A runtime-only resource is distinguishable from a
  service-declared resource.
- A declared but absent resource remains visible as missing; an unavailable
  emulator or service appears as unknown without erasing independently
  available topology information.
- Health remains independent of resource presence and is labeled as liveness.
  A mismatched push endpoint is distinguishable from a confirmed endpoint.
- The default UI opens on the topology. Demonstration diagnostics remain
  available separately, and the topology works without the demo database.
- Review verifies that the composed Workbench reads the existing shared
  network and Pub/Sub emulator without changing Gmail resources, consumer
  data, or message flow.

## Dependencies and unresolved points

The Gmail service implements the first descriptor. Additional services require
only a conforming descriptor and an explicitly configured origin. No
unresolved architecture choice is required for this increment. Remote service
discovery and other messaging providers require separate review.
