CREATE TABLE item_projection.processed_event (
    event_id UUID PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (event_type = 'demo.item.registered'),
    contract_version TEXT NOT NULL CHECK (contract_version = '1'),
    occurred_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL CHECK (length(btrim(source)) > 0),
    correlation_id TEXT,
    causation_id TEXT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    canonical_content_hash BYTEA NOT NULL
        CHECK (octet_length(canonical_content_hash) = 32)
);

CREATE TABLE item_projection.item_projection (
    source TEXT NOT NULL CHECK (length(btrim(source)) > 0),
    item_id TEXT NOT NULL CHECK (length(btrim(item_id)) > 0),
    label TEXT NOT NULL CHECK (length(btrim(label)) > 0),
    registered_event_id UUID NOT NULL UNIQUE,
    PRIMARY KEY (source, item_id)
);
