---
name: feature-lifecycle
description: "Manage robe-platform-event work with the shared eng-lifecycle CLI, from feature startup through verified integration."
---

# Feature lifecycle

Use the shared `eng-lifecycle` CLI from `PATH` for feature startup,
continuation, scoped commits, readiness, architectural review, approval,
integration, and recovery. The repository policy is
`.github/lifecycle.json`; do not duplicate or modify the shared CLI
implementation here.

## Start, continue, and recover

- Follow the `robe-engineer` README's lifecycle CLI setup before use.
- For a **new feature**, run `eng-lifecycle start --repo .` from this
  repository root. Continue on the clean generated branch it reports; do not
  supply a branch name or feature scope.
- For an **active feature**, run
  `eng-lifecycle continue --repo . --feature <reported-branch>`. This verifies
  the current branch and reports working-tree changes without staging,
  switching, or modifying them. Expected, feature-owned uncommitted changes
  do not block continuation.
- Establish ownership from the active task and its declared scope. Do not ask
  again when the task clearly owns the changes. If a change is unexpected or
  its ownership cannot be established, preserve it and ask only about that
  ambiguity before editing, staging, or committing it. Never stash, reset,
  clean, or switch branches to get past a lifecycle blocker.
- Keep known unrelated changes out of scoped commits. If unrelated work
  prevents a clean candidate, stop before readiness review and request only
  what is needed to resolve that conflict.
- `resume` is only for recovering an interrupted post-approval integration;
  it does not resume implementation.
- If `.github/lifecycle.json` is absent, treat this as a lifecycle-adoption
  bootstrap prerequisite. Do not substitute manual lifecycle commands.

## Scoped work, verification, and review

- Use `eng-lifecycle commit --repo . --message "..." --path <path>` with only
  task-scoped paths. The CLI refuses a pre-populated index.
- Run `eng-lifecycle review --repo . --feature <branch> --criteria "..."`
  against the clean committed candidate. The configured readiness checks
  compile the Python sources and tests, then run `tests/unit`.
- Perform architectural review separately from readiness checks and record
  its decision and evidence for the same candidate:
  `eng-lifecycle architecture-review --repo . --feature <branch> --criteria
  "..." --decision accepted --reviewer "..." --evidence "..."`.
  A `changes-requested` decision blocks approval. The review record is bound
  to the candidate commit and tree, acceptance criteria, and quality policy.
  Any candidate change requires fresh readiness and architectural review.
- Existing authorization for routine implementation, verification, and
  lifecycle operations applies throughout the active task; do not request it
  repeatedly. Use `--authorize <category>` for a special check when the task
  has authorized its effects. This flag is a workflow safeguard, not
  permission enforcement or a sandbox.
- The configured pull-request checks are `Unit tests` and
  `Pub/Sub and PostgreSQL integration`. Verify their actual GitHub status;
  configuration alone does not establish server-side branch protection.
- Create the project `.venv` and install the test extra as documented in the
  first vertical-slice guide; the readiness gate invokes that environment
  directly.
- The local end-to-end, migration, and workbench tests can stop/restart the
  Compose PostgreSQL service, require local credentials, or leave test rows.
  Do not run them against the active development stack. Use isolated CI for
  Platform integration/regression verification.

## Approval and integration

- Readiness and architectural review are both required before approval. The
  exact `APPROVED` message must first be given by the user for that specific
  committed candidate and the same acceptance criteria. Never infer it from
  authorization to implement, verify, or review.
- The CLI binds readiness evidence, architectural-review evidence, and
  approval to the candidate commit and tree. `status` and integration reject
  stale records; no source commit may be created after approval.
- Routine authorized lifecycle operations do not need repeated confirmation.
  Preserve the distinct architectural-review and integration-approval gates.
- Use `eng-lifecycle status` to verify approval and `eng-lifecycle integrate`
  or `resume` only after approval. The CLI validates configured CI, review
  policy, merge eligibility, and unresolved conversations; do not bypass a
  failed check, required review, conflict, or safety concern.
- The configured `required_review: false` means an independent GitHub review
  is not required by repository policy; it does not waive the architectural
  review gate. Honor any GitHub-required review or other protection if
  enabled. An administrator bypass requires explicit authorization for that
  specific PR and must not evade failed checks or unresolved concerns.
- Confirm the PR is merged and allow the CLI's safe cleanup and synchronized
  next-branch creation to complete. Report any GitHub protection or CI
  enforcement gap.
