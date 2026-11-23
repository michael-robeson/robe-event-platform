# Conceptual capability model

**Status:** Approved architectural foundation. This is a logical vocabulary
and discussion model, not an inventory of implemented services or a
delivery commitment.

The [platform vision](platform-vision.md) describes the destination; the
[architectural principles](principles.md) guide the choices needed to reach
it. The [architecture overview](overview.md) records the current reference
architecture and links to accepted decisions.

## Capabilities and families

A capability is a cohesive ability to achieve an outcome for a consumer.
A capability family is a discoverable classification of related
responsibilities. Classifications can overlap: a capability can be
discoverable under more than one family without duplicating its
implementation or changing its owner. Families may describe technical
concerns, business responsibilities, or areas of use; they are not mutually
exclusive levels of a mandatory taxonomy.

The following illustrative classifications are neither exhaustive nor a
required catalog. Names and groupings can evolve with demonstrated discovery
needs. They establish no universal domain model, ownership hierarchy,
selected products, interfaces, technologies, or implementation commitments.

| Family | Responsibility | Illustrative capabilities and boundaries |
| --- | --- | --- |
| Access and trust | Establish and enforce permitted interactions | Identity integration, access policy enforcement, and sensitive-information handling; each application retains its domain-specific authorization rules |
| Integration and connectivity | Connect separately owned participants through explicit boundaries | Direct interfaces, event publication and consumption, and external-system adapters; transport does not own business meaning |
| Communication | Support information exchange with people or systems | Notification delivery and communication preferences could be discovery examples; application-specific recipient policy and business intent remain with their owners |
| Persistence | Maintain and retrieve information for an owned responsibility | Consumer-owned persistence mappings, projections, and retrieval; no shared application database or central generic persistence service is implied |
| Intelligence | Support inference, interpretation, or recommendations | Classification or recommendation could be candidates; no AI provider, model, data source, or automated decision authority is selected |
| Commerce | Describe capabilities associated with commercial activity | Pricing or payment integration could be discovery examples; no shared commerce domain, financial rules, or payment implementation is approved |
| Career | Describe capabilities associated with career-related outcomes | Matching or career-document handling could be discovery examples; Robecruit-specific rules, contracts, and schemas remain external |
| Coordination and interaction | Support work spanning steps or participants | Workflow coordination, scheduling, and notification delivery; application policy determines why work happens and what success means |
| Runtime operations | Make platform runtime capabilities observable and operable | Telemetry, runtime configuration, and recovery support; a local demonstration is not a production operating model |

Technical and business capabilities differ in the meaning they own, not in
whether they can be reused. A delivery mechanism can serve multiple domains
without owning their notification policy. A shared business capability would
own an explicitly agreed business responsibility, not every consumer's rules.
For example, notification delivery could be discoverable under Communication
and Coordination and interaction; career-document handling might span Career
and Persistence. Classification alone neither defines a reusable business
capability nor transfers domain ownership. Clarify the responsibility rather
than forcing it into one category.

Product-specific business capabilities, contracts, and schemas remain in
their product repositories. A future platform-owned business capability
needs a reviewed shared need and ownership decision. This model does not
move any Robecruit, FamilyOfSix, or Mailflow domain into this repository.

Shared engineering practices, skills, and lifecycle tooling belong to
`robe-engineering`, not to a platform runtime capability family.
`robe-event-platform` owns platform architecture, runtime capabilities, and
platform-owned contracts, while applying shared engineering guidance locally.
See the [repository ownership boundary](overview.md#engineering-and-platform-ownership)
for the distinction between shared tooling and platform-specific use.

## Component responsibilities

A component realizes part of a capability. A capability may require several
components, and a technical component may support several capabilities.
The roles below describe responsibilities rather than mandatory layers or
deployable units.

| Component role | Responsibility | Boundary |
| --- | --- | --- |
| Application composition | Select capabilities and apply application-specific policy to an outcome | Owns the product experience and domain workflow, not another capability's internals |
| Capability implementation | Deliver a cohesive behavior and enforce its owned rules | Exposes an explicit contract; does not depend on consumers sharing its internal model |
| Contract boundary | Define the supported meaning and interaction expectations | Does not expose incidental implementation or storage details as a public contract |
| Integration adapter | Translate between a capability boundary and an external interface or technology | Owns the mapping, not the external domain or its data |
| State or projection component | Maintain the representation required for its owner's responsibility | Owns persistence mapping and evolution; does not write another owner's state |
| Operational support | Supply visibility and controlled operation for the participating components | Does not turn observations into claims of end-to-end business completion |

For a concrete capability, identify its consumer, owner, outcome, supported
interactions, owned state, dependencies, and failure and recovery obligations.
These questions expose missing decisions; this document does not supply
their implementable answers.

## Composition

Composition combines capabilities through their public boundaries to deliver
an application outcome. It need not use one integration style throughout or
require every application to adopt every family.

The application composition owns the end-to-end outcome and must account for
partial completion across capability boundaries. Each participating
capability remains accountable for its own contracted behavior. Composition
does not imply a central orchestrator, a shared transaction, or a single
owner of all participating state.

For illustration, Robecruit and FamilyOfSix could each need to notify a user
after an application-owned change. Each application would own the reason,
recipient policy, and meaning of that change. A reusable delivery capability
could own delivery behavior without absorbing either application's domain.
An application needing an immediate answer might use a direct interaction;
independent follow-up work might react to a fact through an event.

This example proposes no product requirement, event type, payload, API,
workflow engine, or delivery service. A real composition must first define
ownership, contracts, authorization, failure handling, and completion
semantics. The existing event reliability and persistence decisions remain
in ADRs [0002](../decisions/0002-messaging-and-reliability.md) and
[0003](../decisions/0003-persistence-independence.md).

## Logical organization and physical deployment

Capability families organize architectural thinking. Components identify
responsibilities. Neither maps one-to-one to repositories, processes,
containers, databases, cloud resources, or deployment units.

A logical capability might be realized by a library, components within a
service, several collaborating services, or an external integration.
Conversely, placing components together does not combine their domain
ownership or grant shared write access to their data. These are possible
realizations, not new deployment recommendations.

The accepted initial stack and independent deployability requirements in
[ADR-0001](../decisions/0001-platform-and-deployment-strategy.md) still apply
to platform-owned services and applications. ADR-0003 governs persistence
ownership without requiring database-per-consumer isolation. Any concrete
mapping must respect those decisions and separately justify deployment,
scaling, failure, security, and operational boundaries.

Do not create a service, directory tree, database schema, event catalog, or
cloud resource for each box in this model. Use demonstrated application
needs to select a useful increment, record material choices through ADRs,
and define the relevant contracts before implementation.
