# ADR-0006: Service-Oriented Developer Workbench

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

The local Workbench has grown around the illustrative publisher, projections,
and their diagnostics. Independently maintained services also use the shared
Pub/Sub emulator, but the Workbench has no generic way to learn their identity,
health endpoint, or declared messaging relationships. Adding a dedicated
adapter for each service would couple the Workbench to service implementations
and ownership.

The Workbench must keep three kinds of evidence distinct: a service-declared
relationship, a Pub/Sub resource or relationship discovered at runtime, and
an independently observed liveness result. It remains local-only, read-only,
and outside the event-processing path under
[ADR-0004](0004-local-event-platform-workbench.md). The existing demonstration
and its diagnostics remain useful for reference testing but should not be the
normal service-development interface.

## Decision

Independently maintained services expose a versioned JSON descriptor at
`/.well-known/robe-service.json`. The descriptor declares stable service
identity, a local relative health path, Pub/Sub project, topics, topic roles,
subscriptions, their declared topic relationships, and push or pull delivery.
The version 1 contract is defined by
[`workbench-service-descriptor.v1.schema.json`](../contracts/workbench-service-descriptor.v1.schema.json).
The Workbench obtains descriptors only from explicitly configured HTTP
origins; it does not scan networks or infer service identity from resource
names.

The Workbench queries the local Pub/Sub emulator separately. Its topology
shows declared service relationships separately from runtime-discovered
resources and broker-reported subscription-to-topic and push-endpoint
relationships. Service health is checked independently at the declared
endpoint and labeled as liveness. Missing, mismatched, and unavailable
observations remain distinct; none is evidence of message publication,
delivery, or processing.

Make the interactive topology the default interface, using `@xyflow/react`
for graph nodes, edges, selection, pan/zoom, and controls. This fits the
React/TypeScript Workbench and avoids reimplementing canvas interaction.
Compared with a custom canvas, it supplies the interaction mechanics the
Workbench needs; compared with a graph-analysis library such as Cytoscape, it
fits the React UI without introducing unneeded graph-analysis features. Keep
the existing demonstration observations, event inspection, and diagnostics
in a separate reference view.

The Gmail retrieval service is the first descriptor provider. The local
Workbench composition joins the existing `robe-event-platform-dev` network
and uses its already-running service endpoint and Pub/Sub emulator; it does
not own or modify Gmail resources or consumer data.

Synthetic publication, message inspection, correlation tracking, failure
diagnostics beyond current liveness/configuration observations, performance
benchmarking, remote access, and authorization changes remain deferred.

## Consequences

New services can join the topology by implementing the shared descriptor
contract and adding their origin to local Workbench configuration; no
service-specific Workbench adapter is needed. The Workbench remains a
read-only observer, and an unavailable descriptor does not prevent other
services or discovered Pub/Sub resources from appearing.

The descriptor is a platform-owned integration contract consumed by
independently owned services. It is intentionally specific to the current
Pub/Sub-based local platform. Supporting another broker or remote environment
requires explicit contract and access-control review rather than silently
extending version 1.

This decision supersedes ADR-0004's demonstration-centric interface as the
Workbench's primary experience. ADR-0004's local-only, read-only boundaries
and observation limits continue to apply.
