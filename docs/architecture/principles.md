# Architectural principles

**Status:** Approved architectural foundation. These principles guide
architectural reasoning; they do not amend accepted ADRs or specify
executable contracts.

Use the [platform vision](platform-vision.md) for the destination and the
[conceptual capability model](capability-model.md) for the vocabulary.
Apply these principles together rather than treating one as an absolute
rule. Record material trade-offs through the existing
[ADR process](../decisions/README.md).

## Capability orientation

Organize discussion around what a capability enables, for whom, and under
whose responsibility, rather than starting with services, frameworks, or
cloud resources. Give it a cohesive purpose and a clear boundary.

Reuse must preserve useful meaning. Similar code or terminology is not
sufficient evidence of a shared capability. Prefer a small proven
responsibility over a generic framework built for hypothetical consumers.
A capability is a logical concept, not an automatic instruction to create a
service, repository, or deployment.

## Explicit contracts

Make interactions and expectations explicit at ownership boundaries.
Before implementation depends on an interface, define its supported
operations or facts, semantics, compatibility expectations, failure
behavior, and relevant security and operational obligations.

Distinguish a conceptual responsibility from an implementable contract.
A capability name, example workflow, or logical event element is not a
wire schema. Apply [ADR-0002](../decisions/0002-messaging-and-reliability.md)
to event integration without copying its envelope and reliability rules into
each foundation document. Contracts remain owned and evolved by the
responsible domain; product-specific contracts stay outside this repository.

## Technology independence

Describe capability purpose and domain meaning independently of the
technology implementing them. Keep technology-specific mapping at explicit
boundaries so a change can be assessed without redefining the business
responsibility.

This is a design discipline, not a promise of drop-in portability or a
mandate for abstraction layers. The initial GCP-targeted stack in
[ADR-0001](../decisions/0001-platform-and-deployment-strategy.md) remains
accepted. Supporting another technology requires evidence, implementation,
and review of its trade-offs. Consumer-owned persistence remains governed by
[ADR-0003](../decisions/0003-persistence-independence.md).

## Event-capable, not event-only

Use events when communicating facts and allowing independent reactions fits
the use case. Use direct request-response interactions when an immediate
answer or explicit operation outcome is needed. A composition may need
both; choosing events does not remove coupling or failure modes.

Evaluate latency, consistency, availability, ownership, and recovery before
choosing an interaction style. Distinguish requests to do work from facts
that have occurred. Do not equate transport acceptance with completed
business processing, or infer event sourcing, guaranteed convergence, or
permanent replay from event-driven integration. The accepted event path and
its limits remain in ADRs 0002 and 0003; no additional protocol is selected
here.

## Domain ownership

The owning domain controls its business rules, data, and contracts.
Applications such as Robecruit and FamilyOfSix remain external integrations,
even when they consume the same platform capability. Shared infrastructure
does not grant access to another owner's data or transfer ownership.

Distinguish reusable technical mechanisms from business policy. Promote a
business responsibility to a shared capability only after its meaning,
consumers, and accountable owner have been reviewed. Do not turn the
platform into a central home for product-specific rules or schemas.
Consumer-local state and persistence boundaries follow ADR-0003.

## Evolutionary architecture

Deliver small, useful slices and preserve options where requirements are
uncertain. Design for compatible evolution at boundaries, but avoid
speculative scaffolding and premature physical separation.

Choose physical boundaries from demonstrated deployment, security,
reliability, scaling, and operational needs, within accepted decisions.
Keep changes reviewable and identify migration and recovery implications
before relying on them. New material choices belong in ADRs; revising an
accepted choice requires a new record rather than a silent rewrite.

## Evidence-driven decisions

State the problem, constraints, alternatives, assumptions, and expected
outcomes before choosing a solution. Use focused experiments and measured
application and operational results to test those assumptions, including
evidence against a proposed shared capability.

Separate demonstrated behavior from intended behavior. The local reference
slice is not production validation, and the workbench's observations have
the limits recorded in
[ADR-0004](../decisions/0004-local-event-platform-workbench.md).
Use the vision's outcome measures to assess value; review decisions again
when their assumptions no longer hold.

## Applying the principles

For a proposed increment, identify the capability and owner, the application
outcome, the relevant contracts and accepted decisions, and the evidence
needed to evaluate it. Resolve material gaps before implementation rather
than treating this foundation as authorization to provision resources or
choose technologies. Existing repository guidance on least privilege,
secrets, environment isolation, cost visibility, and controlled changes
continues to apply through ADR-0001.
