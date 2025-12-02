# Research Knowledge Graph System

An agentic backend system that builds semantic knowledge graphs from academic papers using LLM-driven agents. Automatically extracts entities, infers relationships, and enables semantic search and question-answering over research literature.

## Quickstart

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Initialize database
./setup_db.sh

# Run commands
python src/main.py ingest src/examples/sample_papers.json
python src/main.py query papers
```


<details>
<summary><strong>Docker</strong></summary>

```bash
# Set up environment variables
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY, DATABASE_URL)

# Start services
docker-compose up -d

# Ingest papers
docker-compose exec app python src/main.py ingest src/examples/sample_papers.json

# Query papers
docker-compose exec app python src/main.py query papers

# Ask a question
docker-compose exec app python src/main.py query ask_nl_query --query "What papers improve on 3D Gaussian Splatting?"
```

</details>

## Current Graph Visualization ( Based on 90 papers around 3D Gaussian Splatting)

![Zoomed out graph](images/graph_zoomed_out.png)


![Zoomed in graph](images/graph_zoomed_in.png)

The dataset was acquired by running a PDF scraper on the citation link: [https://scholar.google.com/scholar?cites=12323590702419478298&as_sdt=80005&sciodt=0,11&hl=en](https://scholar.google.com/scholar?cites=12323590702419478298&as_sdt=80005&sciodt=0,11&hl=en)

The code to generate the pdf corpus is in `src/google_scholar_down.py`.

### Key Features
- **Multi-Format Ingestion**: Process papers from JSON files or PDF documents
- **LLM-Driven Extraction**: Automatically extracts concepts, methods, datasets, metrics, and authors
- **Cross-Paper Relationships**: Infers semantic relationships between papers (IMPROVES_ON, EXTENDS, COMPARES_TO)
- **Semantic Search**: Vector similarity search using pgvector for finding related papers
- **Question Answering**: RAG-based natural language query interface
- **Graph Visualization**: Interactive HTML visualizations with physics-based layout
- **PostgreSQL Graph Storage**: Uses PostgreSQL as a graph database with typed nodes and edges, with integration via **Supabase**
- **Multi-LLM Support**: Works with OpenAI and Together AI models

## Installation & Setup

### Prerequisites

- **Python 3.9+**
- **PostgreSQL 12+** with pgvector extension
- **OpenAI API key** (or Together AI key)

### Environment Variables

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/paper_graph_db

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Together AI (Optional)
TOGETHER_API_KEY=your_together_api_key_here

# Logging
LOG_LEVEL=INFO
```

### Database Initialization

**Using setup script:**
```bash
./setup_db.sh
```

**Manual setup:**
```bash
createdb paper_graph_db
psql -d paper_graph_db -f sql/schema.sql
psql -d paper_graph_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -d paper_graph_db -c "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS embedding vector(1536);"
```


## Usage

### Ingest Papers

```bash
# From JSON file
python src/main.py ingest src/examples/sample_papers.json

# From directory
python src/main.py ingest ./data/pdfs/

# Skip relationship linking
python src/main.py ingest ./data/pdfs/ --no-link
```


### Query the Graph

```bash
# List all papers
python src/main.py query papers
```

```bash
# Find improvements
python src/main.py query improvements --paper-id <PAPER_UUID>
```
![Zoomed in graph](images/outputs/improvements.png)

```bash
# Get concepts
python src/main.py query concepts --paper-id <PAPER_UUID>
```
![Zoomed in graph](images/outputs/concepts.png)

```bash
# Find similar papers
python src/main.py query similar --paper-id <PAPER_UUID>
```
![Zoomed in graph](images/outputs/similar.png)

```bash
# Ask a question
python src/main.py query ask_nl_query --query "show me paper which is similar to Large Multi-View Gaussian Model for High-Resolution 3D content creation"
```
![Zoomed in graph](images/outputs/ask_nl_query.png)

### Visualize

```bash
# Full graph
python src/main.py visualize --output graph.html

# Subgraph from node
python src/main.py visualize --subgraph <NODE_UUID> --max-depth 2 --output subgraph.html
```

<details>
<summary><strong>Full CLI Command List</strong></summary>

**Ingestion:**
```bash
python src/main.py ingest <file|directory> [--no-link]
```

**Query:**
```bash
python src/main.py query papers [--output results.json]
python src/main.py query improvements --paper-id <UUID>
python src/main.py query concepts --paper-id <UUID>
python src/main.py query datasets --paper-id <UUID>
python src/main.py query similar --paper-id <UUID>
python src/main.py query ask_nl_query --query "<question>"
```

**Visualization:**
```bash
python src/main.py visualize [--output graph.html] [--node-type <type>] [--subgraph <UUID>] [--max-depth <n>] [--limit <n>] [--no-physics]
```

**Direct SQL:**
```bash
psql -d paper_graph_db -f sql/example_queries.sql
```

</details>

---

## Architecture

The system follows a layered agentic architecture:

![System Architecture](images/High_level_Component_Architechture.png)
<details>
<summary><strong>Click to expand architecture details</strong></summary>


The overall system is segregated into:
- **Services Layer:** Orchestrates agent workflows and provides core graph operations, semantic search, and Q&A.
- **Agents Layer:** Autonomous modules, each responsible for a stage in the processing pipeline (ingestion, entity extraction, relationship linking, and validation).
- **Database Layer:** Persists nodes, edges, embeddings, and paper data in a relational+vector database.
- **Utilities:** Offers integrations such as LLM wrappers and PDF text extraction.

The services layer has the following components

- **IngestionService**: Orchestrates the full ingestion pipeline
- **Query Service (Graph)**: Graph operations, cross-paper linking, semantic search
- **QAService**: RAG-based question answering
- **GraphVisualizer**: Generates interactive HTML visualizations
</details>


### Ingress Workflow

![Data Flow](images/Ingestion_flow.png)

<details>
<summary><strong>Click to expand architecture details</strong></summary>
At a high level, the system ingests papers (in PDF or structured formats), extracts key entities (such as concepts, datasets, methods, and authors) using LLM-powered agents, and represents them as nodes and relationships in a property graph stored in PostgreSQL with pgvector for embedding-based similarity. The architecture separates concerns into several layers.

The ingestion pipeline processes papers through multiple agents:
1. **PaperIngestionAgent**: Extracts metadata and chunks text
2. **EntityExtractionAgent**: Extracts entities and intra-paper relationships
3. **ValidationAgent**: Normalizes and validates extracted data
4. **RelationshipLinkingAgent**: Infers cross-paper relationships
</details>

### Query Workflow

![Data Flow](images/Agent_Architecture_Diagram.png)
<details>
<summary><strong>Click to expand architecture details</strong></summary>
Once papers and relationships are ingested into the system, users can query the knowledge graph via both high-level interfaces and direct database access.

1. **Graph Query API:**
   - The system exposes a query service supporting semantic and structural queries across papers, concepts, methods, datasets, and relationships.
   - Users can search by keywords, node type, or apply filters such as year, venue, or entity connections.
   - Example API endpoints:
     - `/search?query="transformers"&node_type=method`
     - `/paper/{uuid}`
     - `/entity/{uuid}/neighbors?depth=2`

2. **Semantic Search:**
   - Embedding-based similarity search lets users find conceptually related nodes or papers, using vector space search over pgvector.
   - Example: Retrieve the top-N most similar papers to a given document or abstract.

4. **Direct SQL Query:**
   - Advanced users may interact directly with the PostgreSQL database using SQL queries (see the [example queries](sql/example_queries.sql)).
   - Custom queries enable deep inspection, joins, and analytic operations unavailable via the mainstream API.

This layered query workflow supports a range of exploratory needs, from semantic exploration to fine-grained database analysis.
</details>



### Database Layer
<details>
<summary><strong>Click to expand architecture details</strong></summary>

- **DatabaseClient**: Manages PostgreSQL connections with pooling ( For our usecase we are using Supabase for managing Postgres workflows)

- **GraphRepository**: Database operations for nodes, edges, and papers
</details>

### Utilities
<details>
<summary><strong>Click to expand architecture details</strong></summary>

- **LLMClient**: Wrapper for OpenAI and Together AI APIs

- **PDF Utilities**: Extract text from PDF documents

</details>

## Database Schema
![Database Schema](images/Database_Schema.png)
<details>
<summary><strong>Click to expand schema details</strong></summary>
### Nodes Table

Stores all entities (papers, concepts, methods, datasets, metrics, authors):
- `id`: UUID primary key
- `node_type`: Type of node
- `label`: Human-readable label
- `properties`: JSONB for flexible metadata
- `embedding`: Vector type (pgvector) for semantic search (papers only)
- `created_at`, `updated_at`: Timestamps

### Edges Table

Stores relationships between nodes:
- `id`: UUID primary key
- `from_node_id`: Source node
- `to_node_id`: Target node
- `edge_type`: Relationship type
- `confidence`: Confidence score (0.0-1.0)
- `properties`: JSONB for rationale, evidence, etc.

### Papers Table

Extended metadata for paper nodes:
- `node_id`: Foreign key to nodes
- `title`, `abstract`: Paper content
- `year`, `venue`: Publication info
- `doi`, `arxiv_id`: Identifiers
- `citation_count`: Citation information

</details>

## Relationship Types

<details>
<summary><strong>Click to expand relationship types</strong></summary>

### Intra-paper edges

- `INTRODUCES`: Paper → Entity (paper introduces a concept/method)
- `USES_CONCEPT`: Paper → Concept (paper uses a concept)
- `USES_DATASET`: Paper → Dataset (paper uses/evaluates on dataset)
- `EVALUATES_WITH`: Paper → Metric (paper uses metric)
- `EVALUATES_ON`: Paper → Dataset (paper evaluates on dataset)
- `AUTHORED_BY`: Paper → Author (attribution)

### Cross-paper edges

- `IMPROVES_ON`: Paper A → Paper B (A improves upon B)
- `EXTENDS`: Paper A → Paper B (A extends B's work)
- `COMPARES_TO`: Paper A → Paper B (A compares to B)
- `SIMILAR_TO`: Paper A ↔ Paper B (bidirectional, similar approaches)
- `REFINES_CONCEPT`: Paper A → Concept → Paper B (A refines concept from B)

</details>

## Design Decisions

<details>
<summary><strong>Click to expand design decisions</strong></summary>


### Relationship Linking Optimization

**Pruning Strategies**: 
- Semantic + dataset filtering (top-k neighbors + shared datasets)
- Shared node filtering (papers sharing entities)

Reduces O(n²) comparisons to O(n*k) where k << n.

### Graph Representation

**Node Types**: Six types (paper, concept, method, dataset, metric, author) balance specificity with generality.

**Dynamic Types**: Single `nodes` table with `node_type` field provides flexibility without schema changes.

**Vector Embeddings**: Stored directly in `nodes` table for simplicity and performance.

### Entity Extraction

**Prompt Design**: Two-stage prompts with low temperature (0.2-0.3) for consistency.

**Validation**: Normalization, deduplication, and validation of extracted entities.

### Query & Question Answering

**RAG Pattern**: Uses Retrieval-Augmented Generation for accuracy and explainability.

**Semantic Search**: Vector embeddings (pgvector) for finding conceptually related papers.



### LLM Provider Support

**Multi-Provider**: Automatic detection based on model name pattern (OpenAI vs Together AI).

**Embedding Limitation**: Currently only OpenAI embeddings supported.

</details>

## Scalability Notes

<details>
<summary><strong>Click to expand scalability considerations</strong></summary>

### Current Limitations

- Sequential processing (one paper at a time)
- No caching of LLM responses
- No batching of database operations
- Full re-processing on updates

### Scaling Strategies

1. **Parallelization**: Process papers in parallel, batch LLM API calls
2. **Caching**: Cache LLM responses and entity extraction results
3. **Batching**: Batch database inserts and relationship inference
4. **Queue System**: Use Celery/RQ for background processing

### Target Performance

- 100 papers: < 1 hour (current)
- 1,000 papers: < 2 hours (with batching)
- 10,000 papers: < 1 day (with parallelization + caching)

</details>
