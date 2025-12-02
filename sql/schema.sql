-- Knowledge Graph Schema for Academic Papers
-- PostgreSQL Database Schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Nodes table: stores all entities (papers, concepts, methods, datasets, metrics, authors)
CREATE TABLE IF NOT EXISTS nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    properties JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create index on node_type for faster queries
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);

-- Create index on label for faster lookups
CREATE INDEX IF NOT EXISTS idx_nodes_label ON nodes(label);

-- Create GIN index on properties for JSONB queries
CREATE INDEX IF NOT EXISTS idx_nodes_properties ON nodes USING GIN(properties);

-- Edges table: stores relationships between nodes
CREATE TABLE IF NOT EXISTS edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    to_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL,
    confidence FLOAT DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    properties JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_node_id, to_node_id, edge_type)
);

-- Create indexes on edges for faster traversal
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_properties ON edges USING GIN(properties);

-- Papers table: extended metadata for paper nodes
CREATE TABLE IF NOT EXISTS papers (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    abstract TEXT,
    year INT,
    venue TEXT,
    doi TEXT,
    arxiv_id TEXT,
    citation_count INT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes on papers
CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_papers_venue ON papers(venue);
CREATE INDEX IF NOT EXISTS idx_papers_arxiv ON papers(arxiv_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to auto-update updated_at
CREATE TRIGGER update_nodes_updated_at BEFORE UPDATE ON nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_edges_updated_at BEFORE UPDATE ON edges
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_papers_updated_at BEFORE UPDATE ON papers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

