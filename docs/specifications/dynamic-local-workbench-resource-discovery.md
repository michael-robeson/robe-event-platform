# Dynamic Local Workbench Resource Discovery

**Status:** Accepted for future implementation  
**Capability owner:** robe-event-platform Workbench  
**Intended users:** Developers using the local Workbench

## Purpose and boundaries

Specify the immediate Workbench increment that discovers and presents the
topics and subscriptions configured in the local Pub/Sub emulator, including
the relationship each subscription reports to its topic.

This is a local, read-only resource inventory. It does not add message
inspection or publication, consumer-processing visibility, event correlation,
GCP integration, multi-tenancy, or access to sensitive payloads or tenant
data. Developer access to the Workbench does not itself authorize access to
that data.

## Context and authoritative sources

- [ADR-0004](../decisions/0004-local-event-platform-workbench.md) defines the
  developer-only Workbench, local read-only boundary, and limits on what
  observations establish.
- [ADR-0005](../decisions/0005-evolutionary-architecture-and-incremental-delivery.md)
  distinguishes this increment from deferred capabilities.
- [ADR-0002](../decisions/0002-messaging-and-reliability.md) remains
  authoritative for messaging semantics; resource discovery does not amend
  those semantics.
- The [first vertical-slice guide](../development/first-vertical-slice.md)
  describes the existing local Workbench and its observation boundaries.

## Expected behavior

1. The Workbench API discovers topics and subscriptions from the configured
   local Pub/Sub emulator at runtime. The inventory is not limited to the
   currently known topic or subscription IDs. Resources added or removed
   while the Workbench is running are reflected after a subsequent refresh,
   without a process restart.
2. The API reports the emulator's topic-to-subscription relationships. The UI
   presents both resource types from the returned inventory and makes each
   subscription's reported topic relationship clear. It does not infer a
   relationship from resource names or hard-coded configuration.
3. Inventory discovery covers all resources visible to the configured local
   emulator; API pagination must not silently truncate the result. A reported
   relationship remains visible even if its topic is absent from the topic
   inventory, and is identified as unresolved rather than discarded or
   fabricated.
4. The UI distinguishes an available empty inventory from an unavailable or
   unknown inventory. If topic or subscription discovery is only partially
   available, it presents the available results and identifies the unavailable
   portion; it must not present an error as an empty result. A discovery
   failure must not hide unrelated Workbench status or consumer observations.
5. The inventory is refreshed on initial load and through the Workbench's
   existing refresh action. The UI renders resources from the current API
   response rather than a fixed set of resource cards.
6. Discovery uses only read operations against the local emulator. It does not
   publish, pull, acknowledge, create, update, or delete Pub/Sub resources; it
   does not write to the database or connect to GCP.
7. Inventory results describe observed resource configuration only. Their
   presence or absence does not establish message publication, delivery,
   consumer processing, acknowledgment, or failure.

The API route and exact response representation, and whether the UI groups
subscriptions under topics or shows them in a separate list, are
implementation choices provided that the behavior above is preserved.

## Acceptance evidence

- With non-default emulator resources configured, the Workbench shows every
  discovered topic and subscription and the emulator-reported relationship,
  including multiple subscriptions for one topic and a topic with no
  subscriptions.
- Adding or removing a resource while the Workbench is running is reflected
  after refresh, without restart or source changes.
- An available empty emulator produces a clear empty state. An unavailable
  emulator is shown as unknown/unavailable, not empty. A failure to discover
  one resource type does not erase successfully discovered resources or
  unrelated status and observation results.
- If an emulator-reported subscription refers to a topic absent from the
  inventory, the UI identifies the relationship as unresolved.
- Verification confirms that discovery performs no resource mutation,
  message publication or consumption, database write, or GCP access, and that
  the UI makes no claims about message or consumer-processing outcomes.

## Dependencies and unresolved points

The local emulator remains the source of truth for the discovered inventory
and reported relationships. No unresolved product or architecture decision is
required for this increment; route shape and presentation layout remain
implementation choices within the specified behavior.
