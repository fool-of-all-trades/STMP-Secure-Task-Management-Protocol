CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- Users table with case-insensitive username, password hash, and account lockout fields
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username CITEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    failed_login_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_login_count >= 0),
    locked_until TIMESTAMPTZ NULL
);

-- Sessions table with token hash, IP tracking, expiry, and resume window
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    client_ip INET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    disconnected_at TIMESTAMPTZ NULL,
    resume_until TIMESTAMPTZ NULL,
    revoked_at TIMESTAMPTZ NULL,
    CONSTRAINT chk_session_expiry CHECK (expires_at > created_at),
    CONSTRAINT chk_resume_window CHECK (
        resume_until IS NULL OR resume_until >= created_at
    )
);

-- Tasks table with title, description, status, timestamps, and foreign key to users
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 256),
    description TEXT NOT NULL DEFAULT '' CHECK (char_length(description) <= 2048),
    status TEXT NOT NULL DEFAULT 'todo',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_task_status CHECK (status IN ('todo', 'done'))
);

-- Authentication logs table to track login attempts, including successful and failed attempts with error codes
CREATE TABLE auth_logs (
    id BIGSERIAL PRIMARY KEY,
    username_attempted VARCHAR(64) NULL,
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    client_ip INET NULL,
    event_type VARCHAR(32) NOT NULL,
    success BOOLEAN NOT NULL,
    error_code INTEGER NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Request history table to track incoming requests, their hashes, response codes, and expiry for caching purposes
CREATE TABLE request_history (
    id BIGSERIAL PRIMARY KEY,
    scope_key VARCHAR(128) NOT NULL,
    request_id VARCHAR(64) NOT NULL,
    message_type VARCHAR(32) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    response_code INTEGER NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_request_history_scope_request UNIQUE (scope_key, request_id),
    CONSTRAINT chk_request_history_expiry CHECK (expires_at > created_at)
);

CREATE INDEX idx_tasks_user_id ON tasks(user_id);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);

CREATE INDEX idx_auth_logs_created_at ON auth_logs(created_at);
CREATE INDEX idx_request_history_expires_at ON request_history(expires_at);

-- Functions and triggers 
-- to automatically update the updated_at timestamp on tasks when they are modified
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tasks_set_updated_at
BEFORE UPDATE ON tasks
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();