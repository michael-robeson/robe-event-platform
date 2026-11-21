#!/bin/bash
set -euo pipefail

: "${ITEM_PROJECTION_DB_PASSWORD:?ITEM_PROJECTION_DB_PASSWORD is required}"

psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --set=app_password="$ITEM_PROJECTION_DB_PASSWORD" <<'SQL'
CREATE ROLE item_projection_app LOGIN PASSWORD :'app_password';
CREATE SCHEMA item_projection AUTHORIZATION item_projection_app;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
SQL

psql \
  --username item_projection_app \
  --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --file /schema/001_initial.sql
