# ADR-0001: Platform and Deployment Strategy

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

The platform needs a common deployment and messaging foundation for
independently deployable services and applications, including a local
development setup that provides useful feedback without implying equivalence
with production. It is GCP-targeted, while detailed operational policies and
some execution models can be decided incrementally. Product applications
such as Mailflow and Robecruit are external integrations; their business
logic, data models, and product-specific contracts remain outside this
repository.

Meaningful alternatives include other cloud providers or self-managed
infrastructure; Kubernetes, VMs, or other managed application runtimes;
Kafka, RabbitMQ, or other messaging systems; and non-PostgreSQL databases.
Infrastructure could be provisioned with provider-specific tools or other
infrastructure-as-code systems, and CI/CD could use a cloud-native or
third-party service.

## Decision

Accept the following initial technology stack:

- **Cloud target:** Google Cloud Platform (GCP).
- **Application execution:** Cloud Run for containerized application
  execution.
- **Asynchronous messaging:** Google Cloud Pub/Sub.
- **Relational database:** PostgreSQL 17 for local development and Cloud SQL
  for PostgreSQL in GCP.
- **Local development:** Docker Compose for coordinating local dependencies
  and services, with the official Pub/Sub emulator for local messaging.
- **Infrastructure provisioning:** Terraform.
- **CI/CD:** GitHub Actions.

Platform-owned services and applications must be independently deployable.
Mailflow, Robecruit, and other products remain external producers or
consumers, not applications or business-logic modules in this repository.

For the initial event-processing implementation, use Google Cloud Pub/Sub
push subscriptions to deliver messages to HTTP endpoints hosted by Cloud Run
services. A consumer returns a successful HTTP response to acknowledge a
message only after its local durable transaction has committed. Pub/Sub
delivery is at least once, so consumers must tolerate duplicate delivery.
Detailed retry, dead-letter, ordering, and idempotency policies will be
defined in ADR-0002.

Cloud Run services are the initial default for application execution, not a
restriction on future Cloud Run jobs, worker pools, or other execution
models.

Apply these architectural principles:

- **Least-privilege identity:** grant users and workloads only the access
  needed for their responsibilities.
- **Managed secrets:** use managed secret storage rather than embedding
  secrets in source, images, or ordinary configuration.
- **Environment isolation:** separate environments to prevent unintended
  access and impact across development, testing, and production.
- **Cost visibility:** make resource costs attributable and visible enough to
  support review and control.
- **Controlled infrastructure changes:** manage infrastructure changes
  through reviewed, traceable, and appropriately authorized processes.

Detailed implementation of these principles, including identity and
environment boundaries, cost controls, Terraform state and execution, and
GitHub Actions authentication and release gates, belongs in subsequent
decisions. They do not all need to be settled before application development
can begin. This ADR does not define event contracts, database schemas,
infrastructure resources, or deployment workflows.

## Consequences

GCP and Cloud Run provide a managed path for deploying containerized,
independently released components without committing the platform to
Kubernetes operations. Cloud Run services provide the initial request-driven
execution model while leaving room for other models as requirements emerge.
Pub/Sub push subscriptions make HTTP handlers the initial consumer interface.
At-least-once delivery means a message can be delivered again, including
after processing commits but before Pub/Sub receives the successful
response; consumers must therefore tolerate duplicates. The local durable
transaction must complete before the handler responds successfully.

PostgreSQL keeps the local relational database in the same major version
family as Cloud SQL, while Docker Compose and the official Pub/Sub emulator
support local development. Terraform and GitHub Actions provide a
provider-aware provisioning tool and a repository-integrated automation
option.

Local-to-cloud consistency is a goal, not a guarantee. A locally run
container can improve application-level consistency, and PostgreSQL 17 can
reduce database version differences, but configuration, networking, identity,
permissions, and managed-service behavior can differ. The Pub/Sub emulator is
useful for local API and message-flow development; it does not reproduce all
production characteristics, such as GCP IAM, quotas, regional behavior, or
managed-service reliability. Cloud integration tests and deployment
validation will still be needed once requirements and environments are
defined. No Cloud SQL emulator is proposed; local development uses PostgreSQL
17 directly.

Application portability and infrastructure portability are distinct.
Containerized services using PostgreSQL and asynchronous messaging through
well-defined application boundaries may be adaptable to another runtime or
provider, but this decision does not promise a provider-neutral application
layer or drop-in portability. Cloud Run, Pub/Sub, and Cloud SQL introduce
GCP-specific operational and integration concerns. Terraform describes
infrastructure but does not make provider resources, IAM, networking, or
service behavior interchangeable; moving providers could require substantial
infrastructure redesign and application changes.

The alternatives could reduce provider coupling or provide different
operational characteristics, but may add operational burden, weaken alignment
with the GCP target, or require different local tooling. These trade-offs
should be revisited if portability, scale, availability, regulatory, or cost
requirements call for them.

This decision establishes an initial direction, not a requirement to settle
every operational detail before implementation. Subsequent ADRs will define
the deferred policies and implementation choices, including Pub/Sub retry,
dead-letter, ordering, and idempotency behavior, environment boundaries,
identity and secret mechanisms, cost controls, and infrastructure change
controls.
