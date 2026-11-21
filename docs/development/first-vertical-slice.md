# First executable vertical slice

This local-only slice demonstrates a stateless HTTP publisher, Pub/Sub push
delivery, and a consumer-owned PostgreSQL projection. It is not a product
integration or a production deployment.

## Prerequisites

- Docker with Docker Compose.
- Python 3.12 or newer.
- Local credentials are not used; the publisher and bootstrap fail unless
  configured for the Compose Pub/Sub emulator.

## Start the local services

If `.env` does not already exist, copy `.env.example` and replace both
placeholder values with different local-only passwords. The ignored `.env`
file is used by Compose; do not commit it.

```sh
if [ ! -e .env ]; then cp .env.example .env; fi
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
docker compose up --build -d pubsub postgres publisher item-projection-consumer ack-fault-proxy
docker compose run --rm pubsub-bootstrap
```

The bootstrap uses the Pub/Sub client library to create `demo-events` and
`demo-item-projection`. The subscription pushes to the test-only proxy, which
normally forwards to the consumer and can inject a one-time lost response
after commit. The publisher is available at `http://127.0.0.1:8080`; the
consumer's local test endpoint is at `http://127.0.0.1:8081`.

The custom PostgreSQL initialization image copies the init script and SQL
into the image instead of bind-mounting them from the workspace. This avoids
permission failures when the container's PostgreSQL user cannot traverse a
private home directory. It initializes the consumer role, schema, and
initial tables only when its data volume is empty. The consumer role owns
only the `item_projection` schema; the publisher has no database credentials. The
password variables are applied during that first initialization, so keep
both password values aligned with the stored role passwords when reusing the
named volume. Changing `.env` does not change existing database passwords.
If initialization fails after PostgreSQL creates the data directory, it will
not automatically rerun on restart; inspect and repair that volume rather
than assuming the schema was created.

## Verify

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

```sh
set -a
. ./.env
set +a
pytest tests/e2e -q
```

The end-to-end suite verifies broker acceptance separately from persistence,
successful projection, duplicate handling, event-ID and business-key
conflicts, database recovery, and a commit-before-ack response loss.

The Pub/Sub emulator supports local HTTP push but does not validate
production HTTPS push authentication or IAM. Its message retention is not
configurable and differs from production. The emulator and local PostgreSQL
do not establish Cloud SQL or production Pub/Sub reliability behavior.
Dead-letter resources and poison-message isolation are intentionally outside
this increment, as are cloud integration tests.
