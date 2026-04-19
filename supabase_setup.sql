-- ============================================================
-- Enstui Ou — Supabase Vector DB Setup
-- Run this ONCE in your Supabase SQL Editor before embedding.
-- Dashboard → SQL Editor → New Query → paste → Run
-- ============================================================

-- 1. Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Main chunks table — stores every embedded text chunk
CREATE TABLE IF NOT EXISTS enstui_chunks (
    id              BIGSERIAL PRIMARY KEY,
    video_id        TEXT        NOT NULL,         -- YouTube video ID
    title           TEXT        NOT NULL,         -- Video title
    published_at    TIMESTAMPTZ,                  -- When video was published
    url             TEXT,                         -- Full YouTube URL
    source_type     TEXT        DEFAULT 'video',  -- 'video' or 'book'
    source_name     TEXT,                         -- Book title if source_type = 'book'
    chunk_index     INTEGER     NOT NULL,         -- Position of chunk within source
    chunk_text      TEXT        NOT NULL,         -- The actual text content
    embedding       vector(768),                  -- Gemini text-embedding-004 dimension
    embedded_at     TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Index for fast similarity search (cosine distance)
CREATE INDEX IF NOT EXISTS enstui_chunks_embedding_idx
ON enstui_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 4. Index for filtering by source type
CREATE INDEX IF NOT EXISTS enstui_chunks_source_idx
ON enstui_chunks (source_type);

-- 5. Index for filtering by video_id
CREATE INDEX IF NOT EXISTS enstui_chunks_video_idx
ON enstui_chunks (video_id);

-- 6. Tracking table — prevents re-embedding the same source twice
CREATE TABLE IF NOT EXISTS enstui_embedded_sources (
    id          BIGSERIAL PRIMARY KEY,
    source_id   TEXT        NOT NULL UNIQUE,  -- video_id or book filename
    source_type TEXT        NOT NULL,         -- 'video' or 'book'
    title       TEXT,
    chunk_count INTEGER,
    embedded_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Similarity search function (used by the RAG query layer)
CREATE OR REPLACE FUNCTION search_enstui (
    query_embedding vector(768),
    match_threshold FLOAT   DEFAULT 0.5,
    match_count     INT     DEFAULT 8,
    source_filter   TEXT    DEFAULT NULL      -- pass 'video' or 'book' to filter, NULL for all
)
RETURNS TABLE (
    id          BIGINT,
    video_id    TEXT,
    title       TEXT,
    url         TEXT,
    source_type TEXT,
    source_name TEXT,
    chunk_index INT,
    chunk_text  TEXT,
    similarity  FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.video_id,
        c.title,
        c.url,
        c.source_type,
        c.source_name,
        c.chunk_index,
        c.chunk_text,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM enstui_chunks c
    WHERE
        1 - (c.embedding <=> query_embedding) > match_threshold
        AND (source_filter IS NULL OR c.source_type = source_filter)
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Done! Your vector database is ready.
-- Next: run embed_transcripts.py to start filling it.
