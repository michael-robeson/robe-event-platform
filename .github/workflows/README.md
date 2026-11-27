# GitHub Actions workflows

Pull requests targeting `develop` run unit tests and the local vertical-slice
end-to-end tests on separate GitHub-hosted runners. The integration job also
checks the audit migration against existing item data and the local workbench.
The unit job also checks generated repository metadata using the pinned
Engineering CLI; it does not regenerate files or rerun tests.
It uses Docker Compose,
the Pub/Sub emulator, and PostgreSQL with temporary credentials; it does not
deploy to GCP. See the [local guide](../../docs/development/first-vertical-slice.md)
for test behavior and emulator limitations.

GitHub branch protection and required checks are not currently enforced for
this repository. A successful CI run is verification, not a protected merge
gate.
