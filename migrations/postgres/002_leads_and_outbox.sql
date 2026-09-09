-- Scan leads (for export and follow-up email) and a durable email outbox.
-- Mirrors migrations/sqlite/002_leads_and_outbox.sql.

CREATE TABLE IF NOT EXISTS scan_leads (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT REFERENCES user_profiles(session_id) ON DELETE CASCADE,
    assessment_id TEXT,
    email TEXT NOT NULL,
    first_name TEXT,
    career_id TEXT,
    career_title TEXT,
    industry TEXT,
    region TEXT,
    career_stage TEXT,
    ai_exposure INTEGER,
    augmentation_potential INTEGER,
    transformation_pressure INTEGER,
    overall_status TEXT,
    rank TEXT,
    xp INTEGER,
    result_json TEXT,
    marketing_consent BOOLEAN NOT NULL DEFAULT FALSE,
    consent_source TEXT,
    consent_at BIGINT,
    created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::bigint,
    updated_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::bigint,
    UNIQUE (assessment_id, email)
);

CREATE INDEX IF NOT EXISTS idx_scan_leads_created ON scan_leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_leads_consent ON scan_leads(marketing_consent, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_leads_email ON scan_leads(email);
CREATE INDEX IF NOT EXISTS idx_scan_leads_career ON scan_leads(career_id);

CREATE TABLE IF NOT EXISTS email_outbox (
    id BIGSERIAL PRIMARY KEY,
    lead_id BIGINT REFERENCES scan_leads(id) ON DELETE CASCADE,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    html_body TEXT NOT NULL,
    text_body TEXT,
    kind TEXT NOT NULL DEFAULT 'results',
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'sending', 'sent', 'failed', 'skipped')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    provider_message_id TEXT,
    created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::bigint,
    updated_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::bigint,
    sent_at BIGINT
);

-- Partial index: the sender only ever scans for work that is still queued.
CREATE INDEX IF NOT EXISTS idx_email_outbox_pending ON email_outbox(created_at) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS idx_email_outbox_status ON email_outbox(status, created_at);
CREATE INDEX IF NOT EXISTS idx_email_outbox_lead ON email_outbox(lead_id);
