# Architecture overview

## Intent

Robe Event Platform is an independent, GCP-targeted reference architecture
for reusable event-driven services. It provides patterns and platform-owned
capabilities that external applications may use; it does not own those
applications or their business behavior.

This is a conceptual view, not a complete deployment design. The initial
technology stack and Pub/Sub push-to-Cloud-Run service direction are accepted
in [ADR-0001](../decisions/0001-platform-and-deployment-strategy.md).
The semantic event model and reliability principles are accepted in
[ADR-0002](../decisions/0002-messaging-and-reliability.md); detailed delivery
policies, environment boundaries, identity mechanisms, and operational
targets remain for subsequent decisions. Consumer-owned persistence mappings
and database-independence principles are accepted in
[ADR-0003](../decisions/0003-persistence-independence.md); implementation
details for ownership boundaries and recovery remain open. The first
executable implementation is a local demonstration; see the [vertical-slice
guide](../development/first-vertical-slice.md).

## Context and boundaries

Applications such as Mailflow and Robecruit are external to this repository.
They may produce events for platform services or consume events those
services publish. They retain ownership of their business rules, application
data, and application-specific contracts. Future products follow the same
boundary.

The repository may own reusable services and the infrastructure required to
run them. It does not own a central application or act as a home for
application-specific integration logic. Integration should use explicitly
documented interfaces once those are designed. ADR-0002 establishes a shared
semantic event envelope; product-specific event contracts are not defined
here.

## Conceptual components

- **External producers and consumers:** independently owned applications
  that exchange events with platform capabilities.
- **Event transport:** Google Cloud Pub/Sub, initially using push
  subscriptions to HTTP endpoints hosted by Cloud Run services. Delivery is
  at least once; consumers must tolerate duplicates. Independent
  subscriptions, unordered delivery by default, and the semantic event
  envelope are established in
  [ADR-0002](../decisions/0002-messaging-and-reliability.md). Operational
  delivery and contract-evolution policies remain to be detailed.
- **Platform services:** independently deployable, reusable event-driven
  capabilities, with clear ownership and runtime boundaries. The local
  item-projection and audit consumers are illustrative local slices, not
  product services.
- **Persistence:** ADR-0003 accepts consumer-owned mappings from semantic
  events to storage. Consumers may share PostgreSQL infrastructure, but
  retain separate data ownership and must not modify another consumer's
  data. Projection correctness is consumer-specific; eventual consistency
  does not guarantee convergence. Physical isolation is left to future
  requirements, and a centralized generic persistence service is not
  assumed.
- **Infrastructure:** separately managed definitions for cloud resources,
  service deployment, and environment configuration.
- **Cross-cutting operations:** identity and access controls, managed
  secrets, environment isolation, cost visibility, observability,
  reliability, and operational procedures. Least privilege, managed
  secrets, isolation, cost visibility, and controlled infrastructure changes
  are principles in ADR-0001; detailed mechanisms and other requirements
  require subsequent decisions.

These are architectural roles, not implemented components.

## Intended repository organization

Add these areas as implementation begins; do not create empty directories in
advance:

- `apps/` — optional platform-owned reference applications or demonstrations.
  It is not a location for Mailflow, Robecruit, or other product code.
- `services/` — reusable, independently deployable services owned by this
  platform.
- `infra/` — cloud resource and deployment definitions, kept distinct from
  service source code.
- `tests/` — cross-component, integration, and architecture-level validation;
  service-specific tests may live with their service where appropriate.

Documentation and ADRs remain under `docs/`. CI/CD workflow definitions, when
introduced, belong under `.github/workflows/`.

## Deployment and lifecycle

The initial target, execution default, provisioning tool, and CI/CD platform
are recorded in ADR-0001. Cloud Run services are the default, with other
execution models available when requirements justify them. Project layout,
environment strategy, networking, release details, and resource provisioning
remain to be specified as implementation needs arise. A deployable
implementation must document its prerequisites and configuration and
provide appropriate tests and operational guidance.

## Open architectural assumptions

Review these remaining assumptions and capture detailed choices as ADRs:

1. Pub/Sub retry and dead-letter thresholds and procedures, any ordering
   keys, idempotency storage, and event wire and versioning policies remain
   to be decided under ADR-0002's accepted principles.
2. Applications retain ownership of their contracts and business data, even
   when they integrate with shared platform services.
3. The platform may include reference applications, but they must remain
   illustrative and separate from production product logic.
4. Detailed identity, secret management, environment isolation, cost
   controls, infrastructure change controls, event evolution, observability,
   and reliability requirements remain to be specified.
5. ADR-0003 accepts persistence independence and ownership principles.
   Enforceable logical boundaries, physical-isolation criteria, migration
   practices, projection completeness, and historical recovery capabilities
   remain to be decided.
