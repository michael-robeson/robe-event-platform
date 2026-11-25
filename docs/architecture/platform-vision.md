# Platform vision

**Status:** Approved architectural foundation. This document describes a
long-term destination, not an accepted implementation plan.

## Destination

Evolve Robe Event Platform into a composable, event-capable application
platform: a foundation of reusable technical and business capabilities that
independently owned applications can combine to deliver their own outcomes.
Applications such as Robecruit and FamilyOfSix are prospective consumers and
sources of learning, not modules to move into this repository.

An application should be able to adopt a useful capability without adopting
the entire platform, sharing its internal data model, or coordinating every
release with other applications. Composition may use direct interactions,
events, or a combination appropriate to the responsibility. Event capability
is a means to decouple work, not a requirement to make every interaction
asynchronous.

## Motivation and boundaries

Repeated technical work and genuinely shared business responsibilities can
slow application delivery and produce inconsistent operational behavior.
Reusable capabilities should reduce that repeated effort while preserving
domain ownership, understandable contracts, and the freedom to evolve.
Reuse is valuable when it improves application outcomes, not simply when it
reduces the number of implementations.

The long-term platform is broader than an event transport or a collection of
database adapters. It is also not a universal application, a shared business
database, or an instruction to centralize all common-looking logic.
Product-specific rules, contracts, and schemas stay in their owning
repositories. A potential cross-application business capability requires
evidence of shared meaning and an explicitly reviewed ownership boundary
before it becomes platform-owned.

This platform is not the shared engineering toolkit. `robe-engineer`
owns cross-repository engineering practices, skills, and lifecycle tooling;
`robe-platform-event` owns platform architecture, runtime capabilities, and
platform-owned contracts. The
[repository ownership boundary](overview.md#engineering-and-platform-ownership)
explains how shared guidance and platform-specific responsibilities coexist.

## Evolutionary growth

Begin with the existing local event-processing reference slice and its
documented limits in the [architecture overview](overview.md). That slice
demonstrates a narrow integration path; it does not demonstrate that the
long-term platform or any product integration already exists.

Grow through small, independently useful increments:

1. Identify a concrete application outcome and the responsibility it needs.
   Record constraints, the current delivery effort, and the cost of doing
   nothing before proposing a shared capability.
2. Demonstrate the smallest useful slice with explicit ownership and
   observable success and failure. Keep application-specific behavior in
   the application.
3. Use a second concrete use case to test whether the meaning, contract,
   and operational needs are actually reusable. Compare extraction with
   retaining separate implementations; do not generalize from names alone.
4. Introduce or expand a shared capability only when the evidence supports
   it. Review material choices through ADRs and define implementable
   contracts before consumers rely on them.
5. Improve, split, replace, or retire capabilities as usage and operating
   evidence reveal their value and cost.

These are learning steps, not scheduled releases or a commitment to build
every family in the [conceptual capability model](capability-model.md).

## Measurable outcomes

Evaluate progress against a baseline for each adopted increment. Record the
measurement period, participating applications, and responsible owner so
comparisons remain meaningful.

| Outcome | Evidence to collect | Desired direction |
| --- | --- | --- |
| Faster application delivery | Elapsed time and engineering effort from a capability need to a working application integration, compared with the prior approach | Less integration effort and shorter lead time |
| Useful reuse | Capabilities used by independently owned applications, with the application-specific adaptations and effort recorded | More demonstrated reuse without growing product-specific branching in the shared capability |
| Independent evolution | Consumer changes or coordinated releases required for each capability change | Fewer forced coordinated changes; compatible changes remain independently adoptable |
| Operational confidence | Use-case-specific success, latency, failure detection, and recovery results under representative conditions | Meet reviewed objectives and reduce undetected or unrecoverable failures |
| Sustainable operation | Delivery and operating cost per relevant application outcome, including support effort | A defensible benefit relative to separate implementations |
| Clear ownership | Adopted capabilities with a named owner, reviewed boundary, documented contract, and support expectations | Every adopted capability is accountable |

These are evaluation measures, not current results, service-level objectives,
or numerical acceptance thresholds. Define baselines and targets during
review of a concrete increment; include unsuccessful trials rather than
counting catalog size as success.

## Relationship to other guidance

The [architectural principles](principles.md) guide trade-offs toward this
destination. The capability model supplies a vocabulary for discussing
responsibilities and composition. The overview connects both to the current
repository and its accepted ADRs.

This vision neither supersedes those ADRs nor defines APIs, event schemas,
database schemas, runtimes, deployment topology, or a migration roadmap.
Implementation requires the relevant decisions and contracts, not an
inference from a conceptual example.
