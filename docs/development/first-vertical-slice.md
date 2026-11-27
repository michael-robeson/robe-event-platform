# First executable vertical slice

This local-only slice demonstrates a stateless HTTP publisher, independent
Pub/Sub push subscriptions, and item and audit projections in PostgreSQL.
It is not a product integration or a production deployment.

## Prerequisites

- Docker with Docker Compose.
- Python 3.12 or newer.
- Local credentials are not used; the publisher and bootstrap fail unless
  configured for the Compose Pub/Sub emulator.

## Start the local services

If `.env` does not already exist, copy `.env.example` and replace the three
consumer and administrator placeholder values with different local-only passwords. For an existing
`.env`, add `AUDIT_PROJECTION_DB_PASSWORD` if needed. The ignored `.env`
file is used by Compose; do not commit it.

```sh
if [ ! -e .env ]; then cp .env.example .env; fi
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
docker compose --profile demo -f compose.yaml -f compose.demo.yaml up --build -d pubsub postgres publisher item-projection-consumer ack-fault-proxy audit-consumer audit-ack-fault-proxy
docker compose --profile demo -f compose.yaml -f compose.demo.yaml run --rm pubsub-bootstrap
```

The bootstrap uses the Pub/Sub client library to create `demo-events` and
`demo-item-projection` and `demo-item-audit`. Each subscription pushes through
its own test-only proxy, which normally forwards to its consumer and can
inject a one-time lost response after commit. The publisher is available at
`http://127.0.0.1:8080`; the item and audit consumer test endpoints are at
`http://127.0.0.1:8081` and `http://127.0.0.1:8082`.

The base `compose.yaml` contains only the reusable Pub/Sub emulator.
Start it for independent service development with
`docker compose up -d pubsub`; this requires no Platform database
credentials. The emulator joins the stable Platform-owned Docker network
`robe-event-platform-dev`. Independently maintained local service Compose
projects can attach to that network and reach the emulator as `pubsub:8085`;
the host-mapped endpoint remains `127.0.0.1:8085`.

The existing publisher, Item and Audit consumers, their test proxies,
PostgreSQL, and demo bootstrap remain in `compose.demo.yaml` behind the
`demo` profile. Their implementation and integration tests remain in this
repository and are run by combining `compose.yaml` and `compose.demo.yaml`
with `--profile demo`.

The custom PostgreSQL initialization image copies the init script and SQL
into the image instead of bind-mounting them from the workspace. This avoids
permission failures when the container's PostgreSQL user cannot traverse a
private home directory. It initializes the consumer role, schema, and
initial tables only when its data volume is empty. The consumer role owns
only the `item_projection` schema; the publisher has no database credentials. The
password variables are applied during that first initialization, so keep
the PostgreSQL and consumer password values aligned with the stored role passwords when reusing the
named volume. Changing `.env` does not change existing database passwords.
If initialization fails after PostgreSQL creates the data directory, it will
not automatically rerun on restart; inspect and repair that volume rather
than assuming the schema was created.

The `audit-migrate` service runs before the audit consumer. It applies the
versioned audit schema in a transaction, including on an existing volume,
without modifying item-consumer data. Re-running it verifies the recorded
version and checksum and confirms the audit login. It does not rotate existing
passwords; an unexpected pre-existing audit schema or role causes an explicit
failure. To run it independently, use
`docker compose --profile demo -f compose.yaml -f compose.demo.yaml run --rm audit-migrate`.
The non-login schema owner is separate from the audit runtime role, which can
insert audit records and read only their IDs and content hashes, but cannot
modify or delete them. The audit projection retains the validated event
fields indefinitely for this demonstration, not arbitrary raw payloads.

## Verify

For lifecycle candidate preparation and metadata checks, install the pinned
shared Engineering CLI into the project virtual environment:

```sh
. .venv/bin/activate
python -m pip install -r .github/requirements-metadata.txt
```

In Fish, activate it with `source .venv/bin/activate.fish` instead. Use
`eng-lifecycle` from this activated environment so scoped commits
automatically generate the Python badge from the staged manifest. The
readiness and CI metadata checks are non-mutating; they fail on drift.
The badge JSON is committed before candidate review and approval. The
version is pinned in the requirements file and may be updated by repository
owners after reviewing a newer Engineering revision.

Unit tests:

```sh
. .venv/bin/activate
pytest tests/unit
```

End-to-end tests require the Compose services above. They use unique test
events and leave existing rows intact; new test rows remain in the demo
database. One scenario stops and restarts the Compose `postgres` service, so
do not run the suite while others depend on it. Tests use the loopback-mapped
demo database and do not target GCP.

For regression verification while the local development stack is in use, use
the `Pub/Sub and PostgreSQL integration` GitHub Actions check on a pull
request. It runs the Compose services and tests on an isolated runner, not
against the developer's running containers or local database.

```sh
set -a
. ./.env
set +a
pytest tests/e2e -q
```

The end-to-end suite verifies broker acceptance separately from persistence,
successful projection, duplicate handling, event-ID and business-key
conflicts, database recovery, and a commit-before-ack response loss. It also
checks independent fan-out and recovery in both directions, concurrent audit
delivery, audit rollback, and database role boundaries.

The migration test writes uniquely identified item records and leaves them in
the database. With PostgreSQL running and the environment exported as above,
`pytest tests/migration -q` verifies that the audit migration preserves those
records and can be repeated. It starts a migration container and requires the
administrator password. Run it only against an authorized local test database.

## Optional read-only workbench

Set `WORKBENCH_DB_PASSWORD` in `.env` to a separate local-only password.
With the services and subscriptions started above, run:

```sh
docker compose --profile demo -f compose.yaml -f compose.demo.yaml -f compose.workbench.yaml up --build -d workbench
```

Open `http://127.0.0.1:8083`. The optional overlay provisions a dedicated
reader role on an existing volume, without changing consumer data. The
provisioning container needs the local administrator password; the API
receives only its reader password. The role has read grants on the two
consumer schemas, not write grants. As with other existing roles, changing
the environment password does not rotate the stored password; restore the
original or explicitly administer rotation. Existing unexpected or
privileged workbench roles cause provisioning to fail.

The UI shows HTTP liveness, a database connection check, known-resource
diagnostics, a dynamically refreshed inventory of emulator topics and
subscriptions with their reported topic relationships, and independently
observed database records. A missing row does not establish failure, and an
unavailable source is unknown. A stored row does not prove publication,
delivery, or acknowledgment. Timestamps are database transaction-time values,
not commit timestamps; sorting and pagination are best effort and do not
establish global order or complete history. The item observation list uses
ledger rows; an item projection without a ledger entry is discoverable only by
inspecting its event UUID. Audit fields are stored projection values, not a
raw event archive. Partial list results do not offer a next-page cursor;
refresh after recovery. The tool has no Docker, publishing, experiment, or
fault-control interface.

After exporting `.env`, `pytest tests/workbench -q` verifies the workbench
against the running local stack. It publishes a uniquely identified demo
event and leaves the resulting rows in the local database. Use it only with
an authorized test stack. The workbench is intended only for trusted local
development, not deployment or production observability.

To verify that resource discovery updates without a Workbench restart, create
resources directly in the local emulator while the Workbench is running. These
commands change only the emulator; the Workbench inventory endpoint performs
read operations only. From the repository root, run:

```sh
PUBSUB_EMULATOR_HOST=127.0.0.1:8085 PUBSUB_PROJECT_ID=robe-local .venv/bin/python - <<'PY'
from google.cloud import pubsub_v1

project = "robe-local"
publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()
topic = publisher.topic_path(project, "workbench-discovery-demo")
empty_topic = publisher.topic_path(project, "workbench-discovery-empty")
publisher.create_topic(request={"name": topic})
publisher.create_topic(request={"name": empty_topic})
for subscription_id in ("workbench-discovery-one", "workbench-discovery-two"):
    subscriber.create_subscription(request={
        "name": subscriber.subscription_path(project, subscription_id),
        "topic": topic,
    })
publisher.transport.close()
subscriber.transport.close()
PY
```

Select **Refresh** in the Workbench. Both topics and subscriptions should
appear, including both subscriptions' reported relationship to the first
topic and the second topic with no subscriptions. Then remove only those
resources from the emulator and refresh again:

```sh
PUBSUB_EMULATOR_HOST=127.0.0.1:8085 PUBSUB_PROJECT_ID=robe-local .venv/bin/python - <<'PY'
from google.cloud import pubsub_v1

project = "robe-local"
publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()
for subscription_id in ("workbench-discovery-one", "workbench-discovery-two"):
    subscriber.delete_subscription(
        request={"subscription": subscriber.subscription_path(project, subscription_id)}
    )
for topic_id in ("workbench-discovery-demo", "workbench-discovery-empty"):
    publisher.delete_topic(request={"topic": publisher.topic_path(project, topic_id)})
publisher.transport.close()
subscriber.transport.close()
PY
```

If these example IDs already exist, substitute a unique suffix in both
commands. The emulator's topic and subscription inventory is independent of
the Workbench's read-only API.

The Pub/Sub emulator supports local HTTP push but does not validate
production HTTPS push authentication or IAM. Its message retention is not
configurable and differs from production. The emulator and local PostgreSQL
do not establish Cloud SQL or production Pub/Sub reliability behavior.
Dead-letter resources and poison-message isolation are intentionally outside
this increment, as are cloud integration tests.
