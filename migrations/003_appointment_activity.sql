-- Run this once in PostgreSQL / AlloyDB before using the OPS dashboard.
CREATE TABLE IF NOT EXISTS appointment_activity (
    id BIGSERIAL PRIMARY KEY,
    appointment_id BIGINT NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    actor_type VARCHAR(30) NOT NULL,
    actor_ref VARCHAR(120),
    action VARCHAR(120) NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS appointment_activity_created_at_idx
    ON appointment_activity (created_at DESC);
