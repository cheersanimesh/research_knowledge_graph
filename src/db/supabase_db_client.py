"""Supabase database client and repository for graph operations."""
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from supabase import create_client, Client
from config import Config
from graph.models import Node, Edge, PaperMetadata
from utils.text_sanitizer import sanitize_node_data, sanitize_string, sanitize_dict

logger = logging.getLogger(__name__)


class SupabaseDatabaseClient:
    """Manages Supabase client connection and provides repository methods."""
    
    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        """Initialize Supabase client."""
        self.supabase_url = supabase_url or Config.SUPABASE_URL
        self.supabase_key = supabase_key or Config.SUPABASE_KEY
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
        
        try:
            self.client: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Supabase client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    # Node operations
    def create_node(self, node: Node) -> UUID:
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
            result = self.client.table("nodes").upsert(
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
        try:
            result = self.client.table("nodes").select("*").eq("id", str(node_id)).execute()
            
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
        try:
            query = self.client.table("nodes").select("*").eq("label", label)
            
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
    
    def get_all_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """Get all nodes of a specific type."""
        try:
            result = self.client.table("nodes").select("*").eq("node_type", node_type).execute()
            
            nodes = []
            for node in result.data:
                # Ensure properties is a dict
                if isinstance(node.get("properties"), str):
                    node["properties"] = json.loads(node["properties"]) if node["properties"] else {}
                nodes.append(node)
            return nodes
        except Exception as e:
            logger.error(f"Error getting nodes by type: {e}")
            return []
    
    # Edge operations
    def create_edge(self, edge: Edge) -> UUID:
        """Insert an edge into the database."""
        try:
            edge_data = {
                "id": str(edge.id),
                "from_node_id": str(edge.from_node_id),
                "to_node_id": str(edge.to_node_id),
                "edge_type": sanitize_string(edge.edge_type),
                "confidence": edge.confidence,
                "properties": sanitize_dict(edge.properties.copy()) if edge.properties else {},
                "created_at": edge.created_at.isoformat() if isinstance(edge.created_at, datetime) else edge.created_at,
                "updated_at": edge.updated_at.isoformat() if isinstance(edge.updated_at, datetime) else edge.updated_at
            }
            
            # Use upsert for INSERT ... ON CONFLICT behavior
            result = self.client.table("edges").upsert(
                edge_data,
                on_conflict="id"
            ).execute()
            
            if result.data:
                return UUID(result.data[0]["id"])
            return edge.id
        except Exception as e:
            logger.warning(f"Error creating edge: {e}")
            raise
    
    def get_edges_from_node(self, node_id: UUID, edge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all edges from a node."""
        try:
            query = self.client.table("edges").select("*").eq("from_node_id", str(node_id))
            
            if edge_type:
                query = query.eq("edge_type", edge_type)
            
            result = query.execute()
            
            edges = []
            for edge in result.data:
                # Ensure properties is a dict
                if isinstance(edge.get("properties"), str):
                    edge["properties"] = json.loads(edge["properties"]) if edge["properties"] else {}
                edges.append(edge)
            return edges
        except Exception as e:
            logger.error(f"Error getting edges from node: {e}")
            return []
    
    def get_edges_to_node(self, node_id: UUID, edge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all edges to a node."""
        try:
            query = self.client.table("edges").select("*").eq("to_node_id", str(node_id))
            
            if edge_type:
                query = query.eq("edge_type", edge_type)
            
            result = query.execute()
            
            edges = []
            for edge in result.data:
                # Ensure properties is a dict
                if isinstance(edge.get("properties"), str):
                    edge["properties"] = json.loads(edge["properties"]) if edge["properties"] else {}
                edges.append(edge)
            return edges
        except Exception as e:
            logger.error(f"Error getting edges to node: {e}")
            return []
    
    # Paper operations
    def create_paper(self, paper: PaperMetadata) -> UUID:
        """Insert or update paper metadata."""
        try:
            paper_data = {
                "node_id": str(paper.node_id),
                "title": sanitize_string(paper.title),
                "abstract": sanitize_string(paper.abstract),
                "year": paper.year,
                "venue": sanitize_string(paper.venue) if paper.venue else None,
                "doi": sanitize_string(paper.doi) if paper.doi else None,
                "arxiv_id": sanitize_string(paper.arxiv_id) if paper.arxiv_id else None,
                "citation_count": paper.citation_count
            }
            
            # Use upsert for INSERT ... ON CONFLICT behavior
            result = self.client.table("papers").upsert(
                paper_data,
                on_conflict="node_id"
            ).execute()
            
            if result.data:
                return UUID(result.data[0]["node_id"])
            return paper.node_id
        except Exception as e:
            logger.error(f"Error creating paper: {e}")
            raise
    
    def get_all_papers(self) -> List[Dict[str, Any]]:
        """Get all papers with their metadata."""
        try:
            # Use Supabase's nested select to join with nodes table
            # This assumes a foreign key relationship exists between papers.node_id and nodes.id
            # If the relationship is properly set up in Supabase, we can use nested select
            # Otherwise, we'll fetch separately
            try:
                # Try to use nested select (requires foreign key relationship in Supabase)
                result = self.client.table("papers").select(
                    "*, nodes!inner(label, properties)"
                ).order("year", desc=True).execute()
                
                papers = []
                for paper in result.data:
                    # Extract node data from nested structure
                    if "nodes" in paper and isinstance(paper["nodes"], list) and len(paper["nodes"]) > 0:
                        node = paper["nodes"][0]
                        paper["label"] = node.get("label")
                        paper["node_properties"] = node.get("properties", {})
                    else:
                        paper["label"] = None
                        paper["node_properties"] = {}
                    papers.append(paper)
                
                return papers
            except Exception:
                # Fallback: fetch papers and nodes separately
                papers_result = self.client.table("papers").select("*").order("year", desc=True).execute()
                
                papers = []
                for paper in papers_result.data:
                    # Fetch corresponding node
                    node_result = self.client.table("nodes").select("label, properties").eq("id", paper["node_id"]).execute()
                    
                    if node_result.data and len(node_result.data) > 0:
                        node = node_result.data[0]
                        paper["label"] = node.get("label")
                        paper["node_properties"] = node.get("properties", {})
                    else:
                        paper["label"] = None
                        paper["node_properties"] = {}
                    
                    papers.append(paper)
                
                return papers
        except Exception as e:
            logger.error(f"Error getting all papers: {e}")
            return []
    
    # Utility methods for direct table access (if needed)
    def get_table(self, table_name: str):
        """Get a Supabase table reference for custom queries."""
        return self.client.table(table_name)
    
    def execute_rpc(self, function_name: str, params: Dict[str, Any] = None):
        """Execute a Postgres function via Supabase RPC."""
        try:
            if params:
                result = self.client.rpc(function_name, params).execute()
            else:
                result = self.client.rpc(function_name).execute()
            return result.data
        except Exception as e:
            logger.error(f"Error executing RPC {function_name}: {e}")
            raise

