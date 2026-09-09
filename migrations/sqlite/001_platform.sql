CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS user_profiles (
    session_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL,
    first_name TEXT NOT NULL,
    career_id TEXT,
    custom_career TEXT,
    career_stage TEXT NOT NULL,
    industry TEXT NOT NULL,
    region TEXT,
    education_level TEXT,
    years_experience INTEGER,
    profile_json TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    updated_at INTEGER NOT NULL DEFAULT (unixepoch()),
    expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_expires ON user_profiles(expires_at);

CREATE TABLE IF NOT EXISTS assessment_sessions (
    assessment_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES user_profiles(session_id) ON DELETE CASCADE,
    career_snapshot TEXT NOT NULL,
    question_ids TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active', 'complete')),
    result_json TEXT,
    xp INTEGER NOT NULL DEFAULT 0,
    rank TEXT NOT NULL DEFAULT 'Explorer',
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    updated_at INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_assessment_session_updated ON assessment_sessions(session_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS assessment_answers (
    assessment_id TEXT NOT NULL REFERENCES assessment_sessions(assessment_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    answer_index INTEGER NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    updated_at INTEGER NOT NULL DEFAULT (unixepoch()),
    PRIMARY KEY (assessment_id, question_id)
);

CREATE TABLE IF NOT EXISTS game_events (
    event_id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessment_sessions(assessment_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    xp_delta INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_game_events_assessment ON game_events(assessment_id, created_at);

CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anonymous_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    properties_json TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics_events(created_at);
CREATE INDEX IF NOT EXISTS idx_analytics_name_created ON analytics_events(event_name, created_at);

