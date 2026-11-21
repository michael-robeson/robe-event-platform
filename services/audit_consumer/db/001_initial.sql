CREATE TABLE audit_projection.audit_event (
    event_id UUID PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (event_type = 'demo.item.registered'),
    contract_version TEXT NOT NULL CHECK (contract_version = '1'),
    occurred_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL CHECK (length(btrim(source)) > 0),
    item_id TEXT NOT NULL CHECK (length(btrim(item_id)) > 0),
    label TEXT NOT NULL CHECK (length(btrim(label)) > 0),
    correlation_id TEXT,
    causation_id TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    canonical_content_hash BYTEA NOT NULL
        CHECK (octet_length(canonical_content_hash) = 32)
);

CREATE INDEX audit_event_item_history
    ON audit_projection.audit_event (source, item_id, occurred_at);

GRANT USAGE ON SCHEMA audit_projection TO audit_projection_app;
GRANT INSERT ON audit_projection.audit_event TO audit_projection_app;
GRANT SELECT (event_id, canonical_content_hash)
    ON audit_projection.audit_event TO audit_projection_app;
