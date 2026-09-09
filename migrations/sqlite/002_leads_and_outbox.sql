-- Scan leads (for export and follow-up email) and a durable email outbox.
-- The outbox exists so a deployment with no internet access (for example the
-- Raspberry Pi) can still record what should be sent and flush it later.

CREATE TABLE IF NOT EXISTS scan_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    marketing_consent INTEGER NOT NULL DEFAULT 0,
    consent_source TEXT,
    consent_at INTEGER,
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    updated_at INTEGER NOT NULL DEFAULT (unixepoch()),
    UNIQUE (assessment_id, email)
);

CREATE INDEX IF NOT EXISTS idx_scan_leads_created ON scan_leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_leads_consent ON scan_leads(marketing_consent, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_leads_email ON scan_leads(email);
CREATE INDEX IF NOT EXISTS idx_scan_leads_career ON scan_leads(career_id);

CREATE TABLE IF NOT EXISTS email_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER REFERENCES scan_leads(id) ON DELETE CASCADE,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    html_body TEXT NOT NULL,
    text_body TEXT,
    kind TEXT NOT NULL DEFAULT 'results',
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued', 'sending', 'sent', 'failed', 'skipped')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    provider_message_id TEXT,
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    updated_at INTEGER NOT NULL DEFAULT (unixepoch()),
    sent_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_email_outbox_status ON email_outbox(status, created_at);
CREATE INDEX IF NOT EXISTS idx_email_outbox_lead ON email_outbox(lead_id);
