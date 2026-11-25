# Architecture overview

## Intent

Robe Event Platform is an independent platform repository with a long-term
vision of composable, event-capable application capabilities. Its current
GCP-targeted reference architecture demonstrates reusable event-driven
services. External applications may use platform-owned capabilities; the
platform does not own those applications or their product-specific behavior.

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
The local read-only workbench and its observation limits are accepted in
[ADR-0004](../decisions/0004-local-event-platform-workbench.md).

## Architectural guidance

Read the foundation documents together, with distinct roles:

| Artifact | Purpose | Authority and limits |
| --- | --- | --- |
| [Platform vision](platform-vision.md) | Destination, motivation, evolutionary growth, and outcome measures | Approved foundation guidance; not a delivery plan or a claim of existing capabilities |
| [Architectural principles](principles.md) | Guidance for evaluating trade-offs toward the vision | Approved foundation guidance; does not silently amend accepted decisions |
| [Conceptual capability model](capability-model.md) | Vocabulary for capabilities, responsibilities, and composition | Approved foundation guidance; not a deployment topology, service inventory, or schema |
| [ADRs](../decisions/README.md) | Record specific architectural choices, alternatives, and consequences | Accepted records govern the choices they settle; changes require a new ADR |
| Implementable contracts | Specify exact interactions, data meaning, compatibility, and relevant operational obligations | Must be separately defined and reviewed by their owners before consumers rely on them; conceptual examples are not contracts |

This overview connects the long-term foundation to current repository
boundaries and accepted decisions. The new foundation selects no additional
technology, runtime, integration protocol, or deployment model. Keep deferred
choices deferred until a concrete increment supplies the requirements and
evidence for review.

If a proposed interpretation of the foundation conflicts with an accepted
ADR, the accepted decision continues to govern until a new ADR explicitly
supersedes it. Implementable contracts must conform to the applicable
accepted decisions; neither a contract nor a conceptual example silently
changes them. Approval of this foundation does not approve its
illustrative capabilities for implementation.

## Context and boundaries

Applications such as Mailflow, Robecruit, and FamilyOfSix are external to this
repository. They may produce events for platform services or consume events
those services publish. The long-term model also allows direct interactions
when justified; no new direct interface is defined here. Applications retain
ownership of their business rules, application data, and application-specific
contracts. Future products follow the same boundary.

The repository may own reusable services and the infrastructure required to
run them. It does not own a central application or act as a home for
application-specific integration logic. Integration should use explicitly
documented interfaces once those are designed. ADR-0002 establishes a shared
semantic event envelope; product-specific event contracts are not defined
here.

### Engineering and platform ownership

`robe-engineer` owns shared engineering practices, reusable skills, and
lifecycle tooling intended for use across repositories. It is not the owner
of this platform's runtime capabilities or their domain contracts.

`robe-platform-event` owns its platform architecture and ADRs, runtime
capability implementations, and platform-owned integration contracts.
Product-specific contracts remain with their external applications.
Platform-specific infrastructure, tests, operational guidance, and local
configuration of shared engineering tooling stay with the platform work
they support.

Consuming a shared skill or lifecycle tool does not transfer platform
architectural authority to `robe-engineer`. Conversely, using engineering
practices here does not make their reusable definitions platform runtime
capabilities. General-purpose improvements belong in `robe-engineer`;
platform-specific application and validation belong here. This boundary
clarifies responsibility without selecting a distribution mechanism,
moving existing files, or changing the accepted runtime and deployment
decisions.

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
