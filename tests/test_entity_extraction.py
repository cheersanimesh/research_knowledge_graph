"""Tests for entity extraction."""
import pytest
from unittest.mock import Mock, patch
from src.graph.models import ExtractedEntity, ExtractedRelationship, EntityExtractionResult
from src.agents.entity_extraction_agent import EntityExtractionAgent
from src.agents.validation_agent import ValidationAgent


def test_extracted_entity_creation():
    """Test creating an ExtractedEntity."""
    entity = ExtractedEntity(
        entity_type="concept",
        label="3D Gaussian Splatting",
        description="A method for novel view synthesis",
        properties={"category": "rendering"}
    )
    assert entity.entity_type == "concept"
    assert entity.label == "3D Gaussian Splatting"
    assert entity.description is not None


def test_extracted_relationship_creation():
    """Test creating an ExtractedRelationship."""
    rel = ExtractedRelationship(
        from_entity_label="Paper A",
        to_entity_label="Concept X",
        relationship_type="INTRODUCES",
        confidence=0.9,
        rationale="Paper A introduces Concept X"
    )
    assert rel.from_entity_label == "Paper A"
    assert rel.relationship_type == "INTRODUCES"
    assert 0.0 <= rel.confidence <= 1.0


def test_validation_agent_normalize_label():
    """Test label normalization."""
    agent = ValidationAgent()
    
    # Test basic normalization
    assert agent._normalize_label("  3d gaussian splatting  ") == "3d Gaussian Splatting"
    assert agent._normalize_label("PSNR") == "PSNR"  # Preserve acronyms
    assert agent._normalize_label("neural radiance fields") == "Neural Radiance Fields"


def test_validation_agent_deduplication():
    """Test entity deduplication."""
    agent = ValidationAgent()
    
    entities = [
        ExtractedEntity(entity_type="concept", label="3D Gaussian Splatting", description="Method 1"),
        ExtractedEntity(entity_type="concept", label="3d gaussian splatting", description="Method 2"),  # Duplicate
        ExtractedEntity(entity_type="concept", label="Neural Radiance Fields", description="Method 3"),
    ]
    
    normalized = agent._normalize_entities(entities, "concept")
    
    # Should have 2 unique entities (duplicate merged)
    assert len(normalized) == 2
    assert normalized[0].label == "3d Gaussian Splatting"  # Normalized
    # Description should be merged (first one kept if both exist)


def test_validation_agent_validate_relationships():
    """Test relationship validation."""
    agent = ValidationAgent()
    
    valid_rel = ExtractedRelationship(
        from_entity_label="Paper A",
        to_entity_label="Concept X",
        relationship_type="INTRODUCES"
    )
    
    invalid_rel = Mock()
    invalid_rel.from_entity_label = ""
    invalid_rel.to_entity_label = "Concept X"
    invalid_rel.relationship_type = "INTRODUCES"
    invalid_rel.confidence = 0.5
    
    relationships = [valid_rel, invalid_rel]
    validated = agent._validate_relationships(relationships)
    
    # Invalid relationship should be filtered out
    assert len(validated) == 1
    assert validated[0].from_entity_label == "Paper A"


@patch('src.agents.entity_extraction_agent.LLMClient')
def test_entity_extraction_agent_mock(mock_llm_class):
    """Test entity extraction agent with mocked LLM."""
    # Setup mock
    mock_llm = Mock()
    mock_llm.complete_json.return_value = {
        "concepts": [
            {
                "entity_type": "concept",
                "label": "3D Gaussian Splatting",
                "description": "A rendering method",
                "properties": {}
            }
        ],
        "methods": [],
        "datasets": [],
        "metrics": [],
        "authors": [],
        "relationships": []
    }
    mock_llm_class.return_value = mock_llm
    
    # Create agent
    agent = EntityExtractionAgent(mock_llm)
    
    # Extract entities
    result = agent.extract_entities("Test paper text about 3D Gaussian Splatting", "Test Paper")
    
    # Verify
    assert isinstance(result, EntityExtractionResult)
    assert len(result.concepts) == 1
    assert result.concepts[0].label == "3D Gaussian Splatting"
    
    # Verify LLM was called
    mock_llm.complete_json.assert_called_once()


def test_entity_extraction_result_structure():
    """Test EntityExtractionResult structure."""
    result = EntityExtractionResult(
        concepts=[
            ExtractedEntity(entity_type="concept", label="Concept 1")
        ],
        methods=[
            ExtractedEntity(entity_type="method", label="Method 1")
        ],
        relationships=[
            ExtractedRelationship(
                from_entity_label="Paper A",
                to_entity_label="Concept 1",
                relationship_type="INTRODUCES"
            )
        ]
    )
    
    assert len(result.concepts) == 1
    assert len(result.methods) == 1
    assert len(result.relationships) == 1
    assert result.datasets == []  # Empty list default


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

