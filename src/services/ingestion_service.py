"""Service for orchestrating paper ingestion pipeline."""
import logging
from typing import List, Dict, Any
from uuid import UUID
from agents.paper_ingestion_agent import PaperIngestionAgent
from agents.entity_extraction_agent import EntityExtractionAgent
from agents.validation_agent import ValidationAgent
from db.repository import GraphRepository
from graph.models import Node, PaperMetadata, ExtractedEntity, Edge
from utils.text_sanitizer import sanitize_string, sanitize_dict

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting papers and building the knowledge graph."""
    
    def __init__(
        self,
        ingestion_agent: PaperIngestionAgent,
        extraction_agent: EntityExtractionAgent,
        validation_agent: ValidationAgent,
        repository: GraphRepository
    ):
        """Initialize ingestion service."""
        self.ingestion_agent = ingestion_agent
        self.extraction_agent = extraction_agent
        self.validation_agent = validation_agent
        self.repository = repository
    
    def ingest_paper(self, paper_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingest a single paper through the full pipeline.
        
        Args:
            paper_input: Dictionary with paper data or file path
        
        Returns:
            Dictionary with ingestion results
        """
        logger.info("Starting paper ingestion pipeline")
        
        # Step 1: Ingest paper
        if isinstance(paper_input, str):
            # Assume it's a file path
            ingested = self.ingestion_agent.ingest_from_file(paper_input)
        elif isinstance(paper_input, dict) and "file_path" in paper_input:
            # Dictionary with file_path key - treat as file
            ingested = self.ingestion_agent.ingest_from_file(paper_input["file_path"])
        else:
            # Assume it's a dictionary with paper data
            ingested = self.ingestion_agent.ingest_from_dict(paper_input)
       
        # Step 2: Extract entities
        title = ingested["metadata"].get("title", "Unknown")
        extraction_result = self.extraction_agent.extract_entities(
            ingested["full_text"],
            title
        )
        # import ipdb; ipdb.set_trace()
        
        # Step 3: Validate and normalize
        validated_result = self.validation_agent.validate_and_normalize(extraction_result)
        
        # Step 4: Create paper node
        paper_node = self._create_paper_node(ingested["metadata"], ingested["full_text"])
        paper_node_id = self.repository.create_node_supabase(paper_node)
        # import ipdb; ipdb.set_trace()
        # Step 5: Create paper metadata
        paper_metadata = PaperMetadata(
            node_id=paper_node_id,
            title=sanitize_string(ingested["metadata"].get("title", "Unknown")),
            abstract=sanitize_string(ingested["metadata"].get("abstract", "")),
            year=ingested["metadata"].get("year"),
            venue=sanitize_string(ingested["metadata"].get("venue")) if ingested["metadata"].get("venue") else None,
            doi=sanitize_string(ingested["metadata"].get("doi")) if ingested["metadata"].get("doi") else None,
            arxiv_id=sanitize_string(ingested["metadata"].get("arxiv_id")) if ingested["metadata"].get("arxiv_id") else None,
            citation_count=ingested["metadata"].get("citation_count")
        )
        self.repository.create_paper(paper_metadata)

        try:
            embedding = self._compute_paper_embedding(
                ingested["metadata"],
                ingested["full_text"]
            )
            self.repository.update_node_embedding(paper_node_id,embedding)
        except Exception as e:
            logger.warning(f"Failed to compute/store embedding for paper {title}: {e}")
        # import ipdb; ipdb.set_trace()
        # Step 6: Create entity nodes and edges
        entity_nodes = {}
        edges_created = []
        
        # Process all entity types
        all_entities = (
            validated_result.concepts +
            validated_result.methods +
            validated_result.datasets +
            validated_result.metrics +
            validated_result.authors +
            validated_result.tasks
        )
        
        for entity in all_entities:
            # Check if node already exists
            # import ipdb; ipdb.set_trace()
            existing = self.repository.find_node_by_label(entity.label, entity.entity_type)
            # import ipdb; ipdb.set_trace()
            if existing:
                entity_node_id = UUID(existing["id"])
                # print(f"using node id {entity_node_id}")
                # import ipdb; ipdb.set_trace()
            else:
                # Create new node
                entity_node = Node(
                    node_type=entity.entity_type,
                    label=entity.label,
                    properties={
                        "description": entity.description,
                        **entity.properties
                    }
                )
                # import ipdb; ipdb.set_trace()

                entity_node_id = self.repository.create_node_supabase(entity_node)
                # print(f"created node id {entity_node_id}")
            # import ipdb; ipdb.set_trace()
            entity_nodes[entity.label] = entity_node_id
            
            if entity.entity_type == 'author' or entity.entity_type == 'authors':
                edge_type = 'AUTHORED_BY'
            else:
                edge_type = 'INTRODUCES'
            # Create INTRODUCES edge from paper to entity
            # import ipdb; ipdb.set_trace()
            introduces_edge = Edge(
                from_node_id=paper_node_id,
                to_node_id=entity_node_id,
                edge_type=edge_type,
                confidence=1.0,
                properties={}
            )
            
            #import ipdb; ipdb.set_trace()
            self.repository.create_edge(introduces_edge)
            edges_created.append(introduces_edge)
        # import ipdb; ipdb.set_trace()
        # Step 7: Create intra-paper relationships
        for rel in validated_result.relationships:
            from_id = entity_nodes.get(rel.from_entity_label)
            to_id = entity_nodes.get(rel.to_entity_label)
            # import ipdb; ipdb.set_trace()
            if from_id and to_id:
                edge = Edge(
                    from_node_id=from_id,
                    to_node_id=to_id,
                    edge_type=rel.relationship_type,
                    confidence=rel.confidence,
                    properties={
                        "rationale": rel.rationale,
                        "evidence_span": rel.evidence_span
                    }
                )
                # import ipdb; ipdb.set_trace()
                self.repository.create_edge(edge)
                edges_created.append(edge)
        
        return {
            "paper_node_id": str(paper_node_id),
            "entities_created": len(entity_nodes),
            "edges_created": len(edges_created),
            "title": title
        }
    
    def _create_paper_node(self, metadata: Dict[str, Any], full_text: str = "") -> Node:
        """Create a paper node from metadata and full text."""
        # Sanitize title and full_text
        title = sanitize_string(metadata.get("title", "Unknown Paper"))
        full_text = sanitize_string(full_text)
        
        properties = {
            "abstract": sanitize_string(metadata.get("abstract", "")),
            "year": metadata.get("year"),
            "venue": sanitize_string(metadata.get("venue")) if metadata.get("venue") else None,
            "doi": sanitize_string(metadata.get("doi")) if metadata.get("doi") else None,
            "arxiv_id": sanitize_string(metadata.get("arxiv_id")) if metadata.get("arxiv_id") else None,
            "authors": metadata.get("authors", []),
            "full_text": full_text
        }
        # Include methods and metrics if extracted in metadata
        if metadata.get("methods"):
            properties["methods"] = sanitize_dict(metadata["methods"]) if isinstance(metadata["methods"], dict) else metadata["methods"]
        if metadata.get("metrics"):
            properties["metrics"] = sanitize_dict(metadata["metrics"]) if isinstance(metadata["metrics"], dict) else metadata["metrics"]
        
        # Include additional comprehensive metadata
        if metadata.get("experimental_setup"):
            properties["experimental_setup"] = sanitize_string(metadata["experimental_setup"]) if isinstance(metadata["experimental_setup"], str) else sanitize_dict(metadata["experimental_setup"])
        if metadata.get("key_results"):
            properties["key_results"] = sanitize_string(metadata["key_results"]) if isinstance(metadata["key_results"], str) else sanitize_dict(metadata["key_results"])
        if metadata.get("limitations"):
            properties["limitations"] = sanitize_string(metadata["limitations"]) if isinstance(metadata["limitations"], str) else sanitize_dict(metadata["limitations"])
        if metadata.get("future_work"):
            properties["future_work"] = sanitize_string(metadata["future_work"]) if isinstance(metadata["future_work"], str) else sanitize_dict(metadata["future_work"])
        if metadata.get("code_availability"):
            properties["code_availability"] = sanitize_string(metadata["code_availability"]) if isinstance(metadata["code_availability"], str) else sanitize_dict(metadata["code_availability"])
        if metadata.get("data_availability"):
            properties["data_availability"] = sanitize_string(metadata["data_availability"]) if isinstance(metadata["data_availability"], str) else sanitize_dict(metadata["data_availability"])
        if metadata.get("supplementary_materials"):
            properties["supplementary_materials"] = sanitize_string(metadata["supplementary_materials"]) if isinstance(metadata["supplementary_materials"], str) else sanitize_dict(metadata["supplementary_materials"])
        if metadata.get("keywords"):
            properties["keywords"] = sanitize_dict(metadata["keywords"]) if isinstance(metadata["keywords"], dict) else metadata["keywords"]
        
        # Sanitize the entire properties dictionary recursively
        properties = sanitize_dict(properties)
        
        return Node(
            node_type="paper",
            label=title,
            properties=properties
        )
    
    def _compute_paper_embedding(self, metadata: Dict[str, Any], full_text: str) -> List[float]:
        """
        Compute an embedding for this paper using:
        - title
        - abstract
        - first N chars of body (as a proxy for method).
        """
        title = metadata.get("title") or ""
        abstract = metadata.get("abstract") or ""
        method_snippet = full_text[:2000]  # simple method-ish chunk

        text = f"Title: {title}\n\nAbstract: {abstract}\n\nBody snippet:\n{method_snippet}"
        llm = self.ingestion_agent.llm  # reuse same LLMClient
        return llm.embed(text)
    


