-- Initialize pgvector extension for semantic search
-- This should be run after the main schema if you need vector embeddings

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to nodes table (if not exists)
-- This is for paper embeddings (1536 dimensions for text-embedding-3-small)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'nodes' AND column_name = 'embedding'
    ) THEN
        ALTER TABLE nodes ADD COLUMN embedding vector(1536);
        
        -- Create index for vector similarity search (HNSW index)
        -- Note: This requires pgvector extension
        CREATE INDEX IF NOT EXISTS idx_nodes_embedding_hnsw 
        ON nodes USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL;
    END IF;
END $$;

