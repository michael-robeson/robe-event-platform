---
name: feature-lifecycle
description: "Manage robe-event-platform work with the shared eng-lifecycle CLI, from startup through verified integration."
---

# Feature lifecycle

Use the shared `eng-lifecycle` CLI from `PATH` for standard feature startup,
scoped commits, readiness, approval, integration, and recovery. The repository
policy is `.github/lifecycle.json`; do not duplicate or modify the shared CLI
implementation here.

## Setup and start

- Follow the `robe-engineering` README's lifecycle CLI setup before use.
- From this repository's root, run `eng-lifecycle start --repo .`. Continue on
  the clean generated branch it reports; do not supply a branch name or scope.
- If `.github/lifecycle.json` is absent, treat that as a lifecycle-adoption
  bootstrap prerequisite. Do not begin ordinary feature work or substitute
  manual lifecycle commands for the configured CLI.
- Preserve dirty work and unrelated branches. Do not stash, reset, clean, or
  create a worktree to get past a lifecycle blocker.

## Commit and readiness

- Use `eng-lifecycle commit --repo . --message "..." --path <path>` and name
  only task-scoped paths. The CLI refuses a pre-populated index.
- Run `eng-lifecycle review --repo . --feature <reported-branch> --criteria
  "..."` on the committed candidate. The configured readiness checks compile
  the Python sources and tests, then run `tests/unit`.
- The configured pull-request checks are `Unit tests` and
  `Pub/Sub and PostgreSQL integration`. Verify their actual GitHub status;
  configuration alone does not establish server-side branch protection.
- Create the project `.venv` and install the test extra as documented in the
  first vertical-slice guide; the readiness gate invokes that environment
  directly.
- The local end-to-end, migration, and workbench tests can stop/restart the
  Compose PostgreSQL service, require local credentials, or leave test rows.
  Run them only against an authorized local test stack and with explicit
  authorization for those effects. CI runs its integration tests on an
  isolated runner.

## Approval and integration

- Read the readiness results and candidate scope before requesting approval.
  `eng-lifecycle approve` requires the user's exact `APPROVED` message for
  that candidate and the same acceptance criteria used for review. Never
  supply that approval on the user's behalf.
- Use `eng-lifecycle status` to verify approval and `eng-lifecycle integrate`
  or `resume` only after approval. The CLI validates the configured CI,
  review policy, merge eligibility, and unresolved conversations; do not
  bypass a failed check, required review, conflict, or safety concern.
- The configured `required_review: false` matches the established
  single-developer policy: an independent GitHub review is not required. The
  owner's exact `APPROVED` message for the candidate and all configured CI
  checks remain mandatory. Honor any GitHub-required review or other
  protection if enabled; an administrator bypass requires explicit
  authorization for that specific PR and must not evade failed checks or
  unresolved concerns.
- Confirm the PR is merged and allow the CLI's safe cleanup and synchronized
  next-branch creation to complete. Report any GitHub protection or CI
  enforcement gap.
