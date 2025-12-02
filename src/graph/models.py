"""Graph data models for nodes and edges."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Node(BaseModel):
    """Represents a node in the knowledge graph."""
    
    id: UUID = Field(default_factory=uuid4)
    node_type: str = Field(..., description="Type: paper, concept, method, dataset, metric, author")
    label: str = Field(..., description="Human-readable label")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties as JSON")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "node_type": "concept",
                "label": "3D Gaussian Splatting",
                "properties": {"description": "A method for novel view synthesis"}
            }
        }


class Edge(BaseModel):
    """Represents an edge (relationship) in the knowledge graph."""
    
    id: UUID = Field(default_factory=uuid4)
    from_node_id: UUID = Field(..., description="Source node ID")
    to_node_id: UUID = Field(..., description="Target node ID")
    edge_type: str = Field(..., description="Relationship type")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "from_node_id": "123e4567-e89b-12d3-a456-426614174000",
                "to_node_id": "223e4567-e89b-12d3-a456-426614174000",
                "edge_type": "IMPROVES_ON",
                "confidence": 0.85,
                "properties": {
                    "rationale": "Paper B introduces adaptive density control",
                    "evidence_span": "Section 3.2"
                }
            }
        }


class PaperMetadata(BaseModel):
    """Extended metadata for paper nodes."""
    
    node_id: UUID
    title: str
    abstract: str
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    citation_count: Optional[int] = None


class ExtractedEntity(BaseModel):
    """Represents an entity extracted from a paper."""
    
    entity_type: str = Field(..., description="concept, method, dataset, metric, author")
    label: str
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class ExtractedRelationship(BaseModel):
    """Represents a relationship extracted from a paper."""
    
    from_entity_label: str
    to_entity_label: str
    relationship_type: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    rationale: Optional[str] = None
    evidence_span: Optional[str] = None


class EntityExtractionResult(BaseModel):
    """Result from entity extraction agent."""
    
    concepts: List[ExtractedEntity] = Field(default_factory=list)
    methods: List[ExtractedEntity] = Field(default_factory=list)
    datasets: List[ExtractedEntity] = Field(default_factory=list)
    metrics: List[ExtractedEntity] = Field(default_factory=list)
    authors: List[ExtractedEntity] = Field(default_factory=list)
    tasks: List[ExtractedEntity] =  Field(default_factory=list) 
    relationships: List[ExtractedRelationship] = Field(default_factory=list)

