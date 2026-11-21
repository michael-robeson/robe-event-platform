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
