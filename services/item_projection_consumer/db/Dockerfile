FROM postgres:17

COPY services/item_projection_consumer/db/001_init.sh /docker-entrypoint-initdb.d/001_init.sh
COPY services/item_projection_consumer/db/001_initial.sql /schema/001_initial.sql
