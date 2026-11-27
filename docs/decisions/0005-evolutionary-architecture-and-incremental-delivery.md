# ADR-0005: Evolutionary Architecture and Incremental Delivery

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

The platform vision calls for reusable capabilities that evolve with
demonstrated needs. The [architectural principles](../architecture/principles.md)
favor small, useful increments, explicit ownership, and evidence over
speculative scaffolding. Strategic foresight should inform current choices,
but should not make every foreseeable capability a current implementation
requirement.

ADR-0001 establishes the initial technology direction; ADR-0002 establishes
messaging and reliability principles; ADR-0003 establishes persistence
ownership; and ADR-0004 establishes the local workbench boundary.
This decision defines an incremental planning approach. It does not amend
those decisions or establish a capability roadmap.

## Decision

For each material implementation increment, identify its consumer or
outcome, owner, scope, acceptance evidence, and applicable accepted ADRs.
Classify relevant architectural considerations as follows:

- **Implement now:** Required to satisfy the increment's scope and
  acceptance criteria, including the security, correctness, and data
  integrity necessary for that scope.
- **Accommodate now:** A foreseeable requirement supported by concrete
  constraints or evidence that should inform current choices. Prefer
  proportionate, reversible decisions, documented constraints, or
  compatible boundaries. Accommodation does not require implementing the
  future capability.
- **Defer:** A capability or complexity without a current requirement or
  sufficient evidence. Keep it unimplemented and, when useful, record the
  evidence or trigger that would justify revisiting it.

Accommodating a future requirement does not by itself justify an abstraction,
framework, interface, or placeholder implementation. Introduce these only
when they serve a current requirement or have evidence-backed value now.

Deferral must not compromise security, correctness, or data integrity for
the current scope. If a concern cannot safely be deferred, resolve it within
the increment or narrow the scope before implementation proceeds.

Cloud hosting, multi-tenancy, sensitive-data protection, cataloging,
observability, and complex business logic are examples to assess, not
implementation commitments. Apply the categories proportionately; do not
treat every possible concern as material to every increment.

## Consequences

Small, cohesive increments remain verifiable against current outcomes while
future constraints can inform decisions without requiring speculative
systems. Recorded deferrals and their triggers make assumptions visible and
provide a basis for revisiting them as evidence changes.

Some deferred needs may require later redesign or migration; accommodating
future change does not guarantee that it will be cost-free. Conversely,
implementing speculative capabilities early adds complexity and maintenance
without demonstrated value. Each increment remains subject to applicable
accepted ADRs and must provide evidence appropriate to its current scope.
