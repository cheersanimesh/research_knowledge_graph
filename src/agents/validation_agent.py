"""Agent for validating and normalizing extracted entities."""
import logging
from typing import List, Dict, Any
from graph.models import ExtractedEntity, EntityExtractionResult
from utils.text_sanitizer import sanitize_string, sanitize_dict

logger = logging.getLogger(__name__)


class ValidationAgent:
    """Agent responsible for validating and normalizing extracted data."""
    
    def __init__(self):
        """Initialize validation agent."""
        pass
    
    def validate_and_normalize(self, extraction_result: EntityExtractionResult) -> EntityExtractionResult:
        """
        Validate and normalize extracted entities.
        
        Args:
            extraction_result: Raw extraction result
        
        Returns:
            Normalized and validated extraction result
        """
        logger.info("Validating and normalizing extracted entities")
        
        # Normalize concepts
        concepts = self._normalize_entities(extraction_result.concepts, "concept")
        
        # Normalize methods
        methods = self._normalize_entities(extraction_result.methods, "method")
        
        # Normalize datasets
        datasets = self._normalize_entities(extraction_result.datasets, "dataset")
        
        # Normalize metrics
        metrics = self._normalize_entities(extraction_result.metrics, "metric")
        
        # Normalize authors
        authors = self._normalize_entities(extraction_result.authors, "author")
        
        # Validate relationships
        relationships = self._validate_relationships(extraction_result.relationships)
        
        return EntityExtractionResult(
            concepts=concepts,
            methods=methods,
            datasets=datasets,
            metrics=metrics,
            authors=authors,
            relationships=relationships
        )
    
    def _normalize_entities(self, entities: List[ExtractedEntity], entity_type: str) -> List[ExtractedEntity]:
        """Normalize entity labels and deduplicate."""
        seen_labels = {}
        normalized = []
        
        for entity in entities:
            if not entity.label or not entity.label.strip():
                continue
            
            # Normalize label
            normalized_label = self._normalize_label(entity.label)
            
            # Check for duplicates (case-insensitive)
            label_key = normalized_label.lower()
            
            if label_key in seen_labels:
                # Merge with existing entity
                existing = seen_labels[label_key]
                # Merge descriptions
                if entity.description and not existing.description:
                    existing.description = entity.description
                # Merge properties
                existing.properties.update(entity.properties)
            else:
                # Sanitize description and properties
                sanitized_description = sanitize_string(entity.description) if entity.description else None
                sanitized_properties = sanitize_dict(entity.properties.copy()) if entity.properties else {}
                
                # Create new normalized entity
                normalized_entity = ExtractedEntity(
                    entity_type=entity_type,
                    label=normalized_label,
                    description=sanitized_description,
                    properties=sanitized_properties
                )
                normalized.append(normalized_entity)
                seen_labels[label_key] = normalized_entity
        
        return normalized
    
    def _normalize_label(self, label: str) -> str:
        """Normalize entity label."""
        # Sanitize first to remove null bytes and problematic characters
        label = sanitize_string(label)
        
        # Strip whitespace
        label = label.strip()
        
        # Remove extra whitespace
        label = " ".join(label.split())
        
        # Capitalize first letter of each word (for consistency)
        # But preserve acronyms (all caps)
        words = label.split()
        normalized_words = []
        for word in words:
            if word.isupper() and len(word) > 1:
                # Preserve acronyms
                normalized_words.append(word)
            else:
                # Capitalize first letter
                normalized_words.append(word.capitalize())
        
        return " ".join(normalized_words)
    
    def _validate_relationships(self, relationships: List) -> List:
        """Validate relationships."""
        validated = []
        
        for rel in relationships:
            # Check required fields
            if not hasattr(rel, 'from_entity_label') or not rel.from_entity_label:
                continue
            if not hasattr(rel, 'to_entity_label') or not rel.to_entity_label:
                continue
            if not hasattr(rel, 'relationship_type') or not rel.relationship_type:
                continue
            
            # Validate confidence
            if not hasattr(rel, 'confidence'):
                rel.confidence = 0.5
            else:
                rel.confidence = max(0.0, min(1.0, float(rel.confidence)))
            
            validated.append(rel)
        
        return validated
    
    def validate_node(self, node_data: Dict[str, Any]) -> bool:
        """Validate node data structure."""
        required_fields = ["node_type", "label"]
        return all(field in node_data and node_data[field] for field in required_fields)
    
    def validate_edge(self, edge_data: Dict[str, Any]) -> bool:
        """Validate edge data structure."""
        required_fields = ["from_node_id", "to_node_id", "edge_type"]
        return all(field in edge_data and edge_data[field] for field in required_fields)

