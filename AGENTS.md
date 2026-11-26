# Agent guidance

- Read the README, architecture overview, and relevant ADRs before changing
  architecture or implementation.
- Record material architectural choices in `docs/decisions/` before relying
  on them in code or infrastructure.
- Keep product-specific business logic, contracts, and schemas outside this
  repository. Treat Mailflow, Robecruit, and other products as external
  integrations.
- Keep service implementation, infrastructure, tests, and documentation in
  their intended boundaries; update directly affected documentation when
  behavior or architecture changes.
- Do not add speculative scaffolding, GCP resources, event contracts, database
  schemas, or CI/CD workflows without an explicit task and reviewed decisions.
- Prefer focused validation relevant to the change; document required setup
  when implementation introduces it.
- Use `eng-lifecycle` from `PATH`, configured by `.github/lifecycle.json`, for
  feature start or continuation, scoped commits, readiness, architectural
  review, approval, and integration. Follow the
  [feature-lifecycle skill](.github/skills/feature-lifecycle/SKILL.md) for
  repository-specific safety requirements.
- For material implementation increments, apply
  [ADR-0005](docs/decisions/0005-evolutionary-architecture-and-incremental-delivery.md)
  proportionately; do not restate it as a separate checklist.
