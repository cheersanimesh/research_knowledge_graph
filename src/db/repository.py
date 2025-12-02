"""Repository for database operations on nodes, edges, and papers."""
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from db.client import DatabaseClient
from graph.models import Node, Edge, PaperMetadata
from supabase import create_client, Client
from config import Config
from utils.text_sanitizer import sanitize_node_data, sanitize_string, sanitize_dict

logger = logging.getLogger(__name__)


class GraphRepository:
    """Repository for graph operations."""
    
    def __init__(self, db_client: DatabaseClient):
        """Initialize repository with database client."""
        self.db = db_client
        self.supabase_url =  Config.SUPABASE_URL
        self.supabase_key = Config.SUPABASE_KEY
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
        
        try:
            self.supabase_client: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Supabase client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    def create_node(self, node: Node) -> UUID:
        """Insert a node into the database."""
        query = """
            INSERT INTO nodes (id, node_type, label, properties, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                label = EXCLUDED.label,
                properties = EXCLUDED.properties,
                updated_at = EXCLUDED.updated_at
            RETURNING id
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    str(node.id),
                    node.node_type,
                    node.label,
                    json.dumps(node.properties),
                    node.created_at,
                    node.updated_at
                )
            )
            result = cursor.fetchone()
            return UUID(result['id'])
    
    def create_node_supabase(self, node: Node) -> UUID:
        """Insert a node into the database."""
        try:
            node_data = {
                "id": str(node.id),
                "node_type": node.node_type,
                "label": node.label,
                "properties": node.properties,
                "created_at": node.created_at.isoformat() if isinstance(node.created_at, datetime) else node.created_at,
                "updated_at": node.updated_at.isoformat() if isinstance(node.updated_at, datetime) else node.updated_at
            }
            
            # Sanitize node data to remove null bytes and other problematic characters
            node_data = sanitize_node_data(node_data)
            
            # Use upsert for INSERT ... ON CONFLICT behavior
            result = self.supabase_client.table("nodes").upsert(
                node_data,
                on_conflict="id"
            ).execute()
            
            if result.data:
                return UUID(result.data[0]["id"])
            return node.id
        except Exception as e:
            logger.error(f"Error creating node: {e}")
            raise
    
    def get_node(self, node_id: UUID) -> Optional[Dict[str, Any]]:
        """Retrieve a node by ID."""
        query = "SELECT * FROM nodes WHERE id = %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (str(node_id),))
            result = cursor.fetchone()
            if result:
                if isinstance(result['properties'], str):
                    result['properties'] = json.loads(result['properties']) if result['properties'] else {}
            return dict(result) if result else None
    
    def get_node_supabase(self, node_id: UUID) -> Optional[Dict[str, Any]]:
        """Retrieve a node by ID."""
        try:
            result = self.supabase_client.table("nodes").select("*").eq("id", str(node_id)).execute()
            
            if result.data and len(result.data) > 0:
                node = result.data[0]
                # Ensure properties is a dict (Supabase returns JSONB as dict)
                if isinstance(node.get("properties"), str):
                    node["properties"] = json.loads(node["properties"]) if node["properties"] else {}
                return node
            return None
        except Exception as e:
            logger.error(f"Error getting node: {e}")
            return None
        
    def find_node_by_label(self, label: str, node_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a node by label (and optionally type)."""
        if node_type:
            query = "SELECT * FROM nodes WHERE label = %s AND node_type = %s LIMIT 1"
            params = (label, node_type)
        else:
            query = "SELECT * FROM nodes WHERE label = %s LIMIT 1"
            params = (label,)
        # import ipdb; ipdb.set_trace()
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            if result:
                if isinstance(result['properties'], str):
                    result['properties'] = json.loads(result['properties']) if result['properties'] else {}
            return dict(result) if result else None
    
    def find_node_by_label_supabase(self, label: str, node_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a node by label (and optionally type)."""
        try:
            query = self.supabase_client.table("nodes").select("*").eq("label", label)
            
            if node_type:
                query = query.eq("node_type", node_type)
            
            result = query.limit(1).execute()
            
            if result.data and len(result.data) > 0:
                node = result.data[0]
                # Ensure properties is a dict
                if isinstance(node.get("properties"), str):
                    node["properties"] = json.loads(node["properties"]) if node["properties"] else {}
                return node
            return None
        except Exception as e:
            logger.error(f"Error finding node by label: {e}")
            return None
    def create_edge(self, edge: Edge) -> UUID:
        """Insert an edge into the database."""
        # Sanitize edge data
        sanitized_edge_type = sanitize_string(edge.edge_type)
        sanitized_properties = sanitize_dict(edge.properties.copy()) if edge.properties else {}
        
        query = """
            INSERT INTO edges (
                id, from_node_id, to_node_id, edge_type, confidence, 
                properties, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                confidence = EXCLUDED.confidence,
                properties = EXCLUDED.properties,
                updated_at = EXCLUDED.updated_at
            RETURNING id
        """
        with self.db.get_cursor() as cursor:
            
            try:
                cursor.execute(
                    query,
                    (
                        str(edge.id),
                        str(edge.from_node_id),
                        str(edge.to_node_id),
                        sanitized_edge_type,
                        edge.confidence,
                        json.dumps(sanitized_properties),
                        edge.created_at,
                        edge.updated_at
                    )
                )
                result = cursor.fetchone()
                return UUID(result['id'])
            except:
                logger.warning("error creating edge")
    
    def get_edges_from_node(self, node_id: UUID, edge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all edges from a node."""
        if edge_type:
            query = "SELECT * FROM edges WHERE from_node_id = %s AND edge_type = %s"
            params = (str(node_id), edge_type)
        else:
            query = "SELECT * FROM edges WHERE from_node_id = %s"
            params = (str(node_id),)
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            for result in results:
                if isinstance(result['properties'], str):
                    result['properties'] = json.loads(result['properties']) if result['properties'] else {}
            return [dict(r) for r in results]
    
    def get_edges_to_node(self, node_id: UUID, edge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all edges to a node."""
        if edge_type:
            query = "SELECT * FROM edges WHERE to_node_id = %s AND edge_type = %s"
            params = (str(node_id), edge_type)
        else:
            query = "SELECT * FROM edges WHERE to_node_id = %s"
            params = (str(node_id),)
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            for result in results:
                if isinstance(result['properties'], str):
                    result['properties'] = json.loads(result['properties']) if result['properties'] else {}
            return [dict(r) for r in results]
    
    def create_paper(self, paper: PaperMetadata) -> UUID:
        """Insert or update paper metadata."""
        query = """
            INSERT INTO papers (
                node_id, title, abstract, year, venue, doi, arxiv_id, citation_count
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (node_id) DO UPDATE SET
                title = EXCLUDED.title,
                abstract = EXCLUDED.abstract,
                year = EXCLUDED.year,
                venue = EXCLUDED.venue,
                doi = EXCLUDED.doi,
                arxiv_id = EXCLUDED.arxiv_id,
                citation_count = EXCLUDED.citation_count
            RETURNING node_id
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    str(paper.node_id),
                    paper.title,
                    paper.abstract,
                    paper.year,
                    paper.venue,
                    paper.doi,
                    paper.arxiv_id,
                    paper.citation_count
                )
            )
            result = cursor.fetchone()
            return UUID(result['node_id'])
    
    def get_all_papers(self) -> List[Dict[str, Any]]:
        """Get all papers with their metadata."""
        query = """
            SELECT p.*, n.label, n.properties as node_properties
            FROM papers p
            JOIN nodes n ON p.node_id = n.id
            ORDER BY p.year DESC NULLS LAST
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            return [dict(r) for r in results]
    
    def get_all_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """Get all nodes of a specific type."""
        query = "SELECT * FROM nodes WHERE node_type = %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (node_type,))
            results = cursor.fetchall()
            for result in results:
                if isinstance(result['properties'], str):
                    result['properties'] = json.loads(result['properties']) if result['properties'] else {}
            return [dict(r) for r in results]
    
    def update_node_embedding(self, node_id: UUID, embedding: List[float]) -> None:
        """Store an embedding vector in the nodes.embedding column."""
        query = "UPDATE nodes SET embedding = %s, updated_at = %s WHERE id = %s"
        now = datetime.utcnow()
        with self.db.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(query, (embedding, now, str(node_id)))

    def search_similar_papers(self, embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """
        Use pgvector similarity to find top-k similar papers.
        Requires nodes.embedding vector column and pgvector extension.
        """
        query = """
            SELECT n.*, p.title, p.year,
                   1 - (n.embedding <-> %s::vector) AS similarity
            FROM nodes n
            JOIN papers p ON p.node_id = n.id
            WHERE n.node_type = 'paper'
              AND n.embedding IS NOT NULL
            ORDER BY n.embedding <-> %s::vector
            LIMIT %s
        """
        with self.db.get_cursor() as cursor:
            # Same embedding used twice for distance + similarity
            cursor.execute(query, (embedding, embedding, k))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def update_node_embedding(self, node_id: UUID, embedding: List[float]) -> None:
        query = "UPDATE nodes SET embedding = %s, updated_at = %s WHERE id = %s"
        now = datetime.utcnow()
        with self.db.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(query, (embedding, now, str(node_id)))
    
    def get_paper_dataset_ids(self, paper_node_id: UUID) :
        """
        Return the set of dataset node IDs connected to this paper.
        We treat any edge from the paper to a node_type = 'dataset' as a dataset usage/intro.
        """
        query = """
            SELECT d.id
            FROM edges e
            JOIN nodes d ON e.to_node_id = d.id
            WHERE e.from_node_id = %s
              AND d.node_type = 'dataset'
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (str(paper_node_id),))
            rows = cursor.fetchall()
            return {UUID(r["id"]) for r in rows}
    
    def get_paper_method_ids(self, paper_node_id: UUID):
        """
        Return the set of method node IDs connected to this paper.
        We treat any edge from the paper to a node_type = 'method' as a method usage/intro.
        """
        query = """
            SELECT m.id
            FROM edges e
            JOIN nodes m ON e.to_node_id = m.id
            WHERE e.from_node_id = %s
              AND m.node_type = 'method'
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (str(paper_node_id),))
            rows = cursor.fetchall()
            return {UUID(r["id"]) for r in rows}
    
    def get_paper_concept_ids(self, paper_node_id: UUID):
        """
        Return the set of concept node IDs connected to this paper.
        We treat any edge from the paper to a node_type = 'concept' as a concept usage/intro.
        """
        query = """
            SELECT c.id
            FROM edges e
            JOIN nodes c ON e.to_node_id = c.id
            WHERE e.from_node_id = %s
              AND c.node_type = 'concept'
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (str(paper_node_id),))
            rows = cursor.fetchall()
            return {UUID(r["id"]) for r in rows}
    
    def get_papers_connected_to_node(self, node_id: UUID) -> List[UUID]:
        """
        Return the set of paper node IDs connected to a given node (dataset/method/concept).
        Papers can connect via edges from paper to node.
        """
        query = """
            SELECT DISTINCT p.node_id
            FROM edges e
            JOIN papers p ON e.from_node_id = p.node_id
            WHERE e.to_node_id = %s
              AND p.node_id IS NOT NULL
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (str(node_id),))
            rows = cursor.fetchall()
            return [UUID(r["node_id"]) for r in rows]
    
    def get_similar_papers_for_node(
        self,
        paper_node_id: UUID,
        k: int = 10
    ) -> List[dict]:
        """
        Return top-k most similar paper rows to the given paper_node_id using pgvector.
        """
        query = """
            WITH q AS (
                SELECT embedding
                FROM nodes
                WHERE id = %s
                  AND embedding IS NOT NULL
            )
            SELECT n.id AS node_id,
                   n.node_type,
                   n.label,
                   p.title,
                   p.year,
                   1 - (n.embedding <-> q.embedding) AS similarity
            FROM nodes n
            JOIN papers p ON p.node_id = n.id
            CROSS JOIN q
            WHERE n.node_type = 'paper'
              AND n.id <> %s
              AND n.embedding IS NOT NULL
            ORDER BY n.embedding <-> q.embedding
            LIMIT %s
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (str(paper_node_id), str(paper_node_id), k))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    


