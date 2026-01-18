-- Face-Based Photo Segregation System - SQLite Schema
-- Authoritative registry and job/batch state management

-- ============================================================================
-- PERSON REGISTRY (Authoritative)
-- ============================================================================

-- Persons table - core identity records
CREATE TABLE IF NOT EXISTS persons (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    output_folder_rel TEXT NOT NULL UNIQUE,  -- Relative folder under output root
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Person embeddings - bounded collection per person (FIFO trimming)
CREATE TABLE IF NOT EXISTS person_embeddings (
    embedding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    embedding BLOB NOT NULL,  -- 512-dim float32 vector serialized
    source_type TEXT NOT NULL DEFAULT 'reference',  -- 'reference' or 'learned'
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES persons(person_id)
);

CREATE INDEX IF NOT EXISTS idx_person_embeddings_person 
    ON person_embeddings(person_id);

-- Person centroids - precomputed centroid for faster matching
CREATE TABLE IF NOT EXISTS person_centroids (
    person_id INTEGER PRIMARY KEY REFERENCES persons(person_id) ON DELETE CASCADE,
    centroid BLOB NOT NULL,  -- 512-dim float32 vector serialized
    embedding_count INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES persons(person_id)
);

-- ============================================================================
-- JOB CONFIGURATION
-- ============================================================================

-- Job configuration - single active job at a time
CREATE TABLE IF NOT EXISTS job_config (
    config_id INTEGER PRIMARY KEY CHECK (config_id = 1),  -- Singleton
    source_root TEXT,
    output_root TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Initialize singleton config row
INSERT OR IGNORE INTO job_config (config_id) VALUES (1);

-- ============================================================================
-- JOB EXECUTION
-- ============================================================================

-- Jobs table - one job per processing run
CREATE TABLE IF NOT EXISTS jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_root TEXT NOT NULL,
    output_root TEXT NOT NULL,
    total_images INTEGER NOT NULL DEFAULT 0,
    processed_images INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'created',  -- created, running, completed, failed
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT
);

-- Images table - all discovered images for a job
CREATE TABLE IF NOT EXISTS images (
    image_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    source_path TEXT NOT NULL,  -- Full path on external HDD
    filename TEXT NOT NULL,  -- Original filename
    extension TEXT NOT NULL,  -- .jpg, .jpeg, .arw
    sha256 TEXT,  -- File hash for deduplication
    ordering_idx INTEGER NOT NULL,  -- Deterministic ordering index
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    UNIQUE(job_id, source_path)
);

CREATE INDEX IF NOT EXISTS idx_images_job ON images(job_id);
CREATE INDEX IF NOT EXISTS idx_images_ordering ON images(job_id, ordering_idx);
CREATE INDEX IF NOT EXISTS idx_images_sha256 ON images(sha256);

-- Batches table - atomic 50-image batches
CREATE TABLE IF NOT EXISTS batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    start_idx INTEGER NOT NULL,  -- First image ordering_idx
    end_idx INTEGER NOT NULL,    -- Last image ordering_idx (inclusive)
    state TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING, PROCESSING, COMMITTING, COMMITTED
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    committed_at TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_batches_job ON batches(job_id);
CREATE INDEX IF NOT EXISTS idx_batches_state ON batches(state);

-- ============================================================================
-- IMAGE PROCESSING RESULTS
-- ============================================================================

-- Image results - per-image face detection and matching results
CREATE TABLE IF NOT EXISTS image_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL REFERENCES images(image_id) ON DELETE CASCADE,
    batch_id INTEGER NOT NULL REFERENCES batches(batch_id) ON DELETE CASCADE,
    face_count INTEGER NOT NULL DEFAULT 0,
    matched_count INTEGER NOT NULL DEFAULT 0,
    unknown_count INTEGER NOT NULL DEFAULT 0,
    matched_person_ids TEXT,  -- JSON array of person_ids
    processed_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (image_id) REFERENCES images(image_id),
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id),
    UNIQUE(image_id)
);

CREATE INDEX IF NOT EXISTS idx_image_results_batch ON image_results(batch_id);

-- ============================================================================
-- COMMIT LOG (Append-Only)
-- ============================================================================

-- Commit log - tracks all output writes for idempotency and reconciliation
CREATE TABLE IF NOT EXISTS commit_log (
    commit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(batch_id),
    image_id INTEGER NOT NULL REFERENCES images(image_id),
    person_id INTEGER NOT NULL REFERENCES persons(person_id),
    output_filename TEXT NOT NULL,  -- Deterministic filename
    output_path TEXT NOT NULL,      -- Full path on external HDD
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, written, verified
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    verified_at TEXT,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id),
    FOREIGN KEY (image_id) REFERENCES images(image_id),
    FOREIGN KEY (person_id) REFERENCES persons(person_id)
);

CREATE INDEX IF NOT EXISTS idx_commit_log_batch ON commit_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_commit_log_status ON commit_log(status);
CREATE INDEX IF NOT EXISTS idx_commit_log_output ON commit_log(output_path);

-- ============================================================================
-- SCHEMA VERSION
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);

