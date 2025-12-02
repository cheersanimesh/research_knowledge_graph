"""Agent for inferring cross-paper semantic relationships."""
import logging
from typing import List, Dict, Any, Tuple
from uuid import UUID
from utils.llm import LLMClient
from config import Config
from graph.models import Edge

logger = logging.getLogger(__name__)


class RelationshipLinkingAgent:
    """Agent responsible for inferring cross-paper semantic relationships."""
    
    def __init__(self, llm_client: LLMClient):
        """Initialize relationship linking agent."""
        self.llm = llm_client
    
    def infer_relationships(
        self,
        paper_nodes: List[Dict[str, Any]],
        concept_nodes: List[Dict[str, Any]],
        method_nodes: List[Dict[str, Any]]
    ) -> List[Edge]:
        """
        Infer cross-paper semantic relationships.
        
        Args:
            paper_nodes: List of paper node dictionaries
            concept_nodes: List of concept node dictionaries
            method_nodes: List of method node dictionaries
        
        Returns:
            List of Edge objects representing cross-paper relationships
        """
        logger.info(f"Inferring relationships across {len(paper_nodes)} papers")
        
        edges = []
        
        # Compare each pair of papers
        for i, paper1 in enumerate(paper_nodes):
            for paper2 in paper_nodes[i+1:]:
                relationships = self._compare_papers(paper1, paper2, concept_nodes, method_nodes)
                edges.extend(relationships)
        
        return edges
    
    def _compare_papers(
        self,
        paper1: Dict[str, Any],
        paper2: Dict[str, Any],
        concept_nodes: List[Dict[str, Any]],
        method_nodes: List[Dict[str, Any]]
    ) -> List[Edge]:
        """Compare two papers and infer relationships."""
        # Get paper metadata
        title1 = paper1.get("label", "") or paper1.get("properties", {}).get("title", "")
        title2 = paper2.get("label", "") or paper2.get("properties", {}).get("title", "")
        
        if not title1 or not title2:
            return []
        
        # Use LLM to infer relationships
        relationships = self._infer_with_llm(paper1, paper2, concept_nodes, method_nodes)
        
        return relationships
    
    def _infer_with_llm(
        self,
        paper1: Dict[str, Any],
        paper2: Dict[str, Any],
        concept_nodes: List[Dict[str, Any]],
        method_nodes: List[Dict[str, Any]]
    ) -> List[Edge]:
        """Use LLM to infer relationships between two papers."""
        # Check if debug mode is enabled
        if Config.DEBUG:
            logger.info("DEBUG mode: Returning default relationship inference (skipping LLM call)")
            # import ipdb; ipdb.set_trace()
            return self._get_default_relationships(paper1, paper2)
        
        system_prompt = """You are an expert at analyzing relationships between academic papers.
Given two papers, determine if there are semantic relationships such as:

1. IMPROVES_ON: Paper B improves upon Paper A's method/approach
2. EXTENDS: Paper B extends Paper A's work
3. COMPARES_TO: Paper B compares its approach to Paper A
4. SIMILAR_TO: Papers use similar approaches
5. REFINES_CONCEPT: Paper B refines a concept introduced in Paper A

For each relationship, provide:
- relationship_type: One of the types above
- confidence: Confidence score (0.0-1.0)
- rationale: Explanation of the relationship
- evidence_concepts: List of concept/method labels that support this relationship

Return a JSON array of relationships. If no clear relationship exists, return an empty array."""
        
        # Build context about papers
        paper1_info = self._build_paper_info(paper1)
        paper2_info = self._build_paper_info(paper2)
        
        # Get relevant concepts/methods
        concepts_str = ", ".join([c.get("label", "") for c in concept_nodes[:20]])  # Limit for context
        methods_str = ", ".join([m.get("label", "") for m in method_nodes[:20]])
        # import ipdb; ipdb.set_trace()
        user_prompt = f"""Analyze the relationship between these two papers:

Paper 1:
{paper1_info}

Paper 2:
{paper2_info}

Available concepts: {concepts_str}
Available methods: {methods_str}

Determine if there are semantic relationships between these papers. Return JSON array with format:
[
  {{
    "relationship_type": "IMPROVES_ON",
    "confidence": 0.85,
    "rationale": "Paper 2 improves upon Paper 1 by introducing adaptive density control",
    "evidence_concepts": ["3D Gaussian Splatting", "Adaptive Density Control"]
  }}
]"""
        
        try:
            result_json = self.llm.complete_json(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=12000
            )
            
            # Parse relationships
            relationships = []
            # Handle if result_json is a dict (single relationship)
            if isinstance(result_json, dict):
                result_json = [result_json]
            if isinstance(result_json, list):
                for rel_data in result_json:
                    if isinstance(rel_data, dict):
                        edge = Edge(
                            from_node_id=UUID(paper2["id"]) if rel_data.get("relationship_type") in ["IMPROVES_ON", "EXTENDS", "REFINES_CONCEPT"] else UUID(paper1["id"]),
                            to_node_id=UUID(paper1["id"]) if rel_data.get("relationship_type") in ["IMPROVES_ON", "EXTENDS", "REFINES_CONCEPT"] else UUID(paper2["id"]),
                            edge_type=rel_data.get("relationship_type", "SIMILAR_TO"),
                            confidence=float(rel_data.get("confidence", 0.5)),
                            properties={
                                "rationale": rel_data.get("rationale", ""),
                                "evidence_concepts": rel_data.get("evidence_concepts", [])
                            }
                        )
                        relationships.append(edge)
            
            return relationships
        except Exception as e:
            logger.warning(f"Failed to infer relationship via LLM between papers: {e}")
            return []
    
    def _get_default_relationships(
        self,
        paper1: Dict[str, Any],
        paper2: Dict[str, Any]
    ) -> List[Edge]:
        """Return default relationships for debug mode."""
        try:
            # Return a sample relationship indicating similarity
            edge = Edge(
                from_node_id=UUID(paper1["id"]),
                to_node_id=UUID(paper2["id"]),
                edge_type="SIMILAR_TO",
                confidence=0.75,
                properties={
                    "rationale": "Papers appear to be related based on similar topics (DEBUG mode)",
                    "evidence_concepts": ["3D Gaussian Splatting", "Neural Rendering"]
                }
            )
            return [edge]
        except Exception as e:
            logger.warning(f"Failed to create default relationship in debug mode: {e}")
            return []
    
    def _build_paper_info(self, paper: Dict[str, Any]) -> str:
        """Build a comprehensive summary string for a paper."""
        parts = []
        
        label = paper.get("label", "")
        if label:
            parts.append(f"Title: {label}")
        
        props = paper.get("properties", {})
        if props.get("title") and props["title"] != label:
            parts.append(f"Title: {props['title']}")
        
        # Authors
        if props.get("authors"):
            authors_str = ", ".join(props["authors"]) if isinstance(props["authors"], list) else str(props["authors"])
            parts.append(f"Authors: {authors_str}")
        
        # Year
        if props.get("year"):
            parts.append(f"Year: {props['year']}")
        
        # Arxiv ID / DOI
        if props.get("arxiv_id"):
            parts.append(f"ArXiv ID: {props['arxiv_id']}")
        if props.get("doi"):
            parts.append(f"DOI: {props['doi']}")
        
        # Abstract (full, not truncated)
        if props.get("abstract"):
            parts.append(f"\nAbstract:\n{props['abstract']}")
        
        # Full Text
        if props.get("full_text"):
            full_text = props["full_text"]
            # Include the full text for comprehensive comparison
            parts.append(f"\nFull Text:\n{full_text}")
        
        # Keywords
        if props.get("keywords"):
            keywords_str = ", ".join(props["keywords"]) if isinstance(props["keywords"], list) else str(props["keywords"])
            parts.append(f"\nKeywords: {keywords_str}")
        
        # Methods
        if props.get("methods"):
            parts.append("\nMethods:")
            for method in props["methods"]:
                if isinstance(method, dict):
                    method_parts = []
                    if method.get("method_name"):
                        method_parts.append(f"  - Method Name: {method['method_name']}")
                    if method.get("description"):
                        method_parts.append(f"    Description: {method['description']}")
                    if method.get("key_components"):
                        components = ", ".join(method["key_components"]) if isinstance(method["key_components"], list) else str(method["key_components"])
                        method_parts.append(f"    Key Components: {components}")
                    if method.get("implementation_details"):
                        method_parts.append(f"    Implementation: {method['implementation_details']}")
                    if method.get("parameters"):
                        method_parts.append(f"    Parameters: {method['parameters']}")
                    if method_parts:
                        parts.append("\n".join(method_parts))
        
        # Key Results
        if props.get("key_results"):
            parts.append(f"\nKey Results:\n{props['key_results']}")
        
        # Metrics
        if props.get("metrics"):
            parts.append("\nMetrics:")
            for metric in props["metrics"]:
                if isinstance(metric, dict):
                    metric_parts = []
                    if metric.get("metric_name"):
                        metric_parts.append(f"  - {metric['metric_name']}")
                    if metric.get("description"):
                        metric_parts.append(f"    Description: {metric['description']}")
                    if metric.get("reported_values"):
                        values = ", ".join(map(str, metric["reported_values"])) if isinstance(metric["reported_values"], list) else str(metric["reported_values"])
                        metric_parts.append(f"    Values: {values}")
                    if metric.get("datasets_used"):
                        metric_parts.append(f"    Datasets: {metric['datasets_used']}")
                    if metric_parts:
                        parts.append("\n".join(metric_parts))
        
        # Experimental Setup
        if props.get("experimental_setup"):
            setup = props["experimental_setup"]
            if isinstance(setup, dict):
                parts.append("\nExperimental Setup:")
                if setup.get("datasets"):
                    datasets = ", ".join(setup["datasets"]) if isinstance(setup["datasets"], list) else str(setup["datasets"])
                    parts.append(f"  Datasets: {datasets}")
                if setup.get("hardware"):
                    parts.append(f"  Hardware: {setup['hardware']}")
                if setup.get("software"):
                    parts.append(f"  Software: {setup['software']}")
                if setup.get("evaluation_protocol"):
                    parts.append(f"  Evaluation Protocol: {setup['evaluation_protocol']}")
        
        # Limitations
        if props.get("limitations"):
            limitations = props["limitations"]
            if isinstance(limitations, list):
                limitations_str = "\n  - ".join(limitations)
                parts.append(f"\nLimitations:\n  - {limitations_str}")
            else:
                parts.append(f"\nLimitations: {limitations}")
        
        # Future Work
        if props.get("future_work"):
            future_work = props["future_work"]
            if isinstance(future_work, list):
                future_work_str = "\n  - ".join(future_work)
                parts.append(f"\nFuture Work:\n  - {future_work_str}")
            else:
                parts.append(f"\nFuture Work: {future_work}")
        
        # Code Availability
        if props.get("code_availability"):
            parts.append(f"\nCode Availability: {props['code_availability']}")
        
        # Venue
        if props.get("venue"):
            parts.append(f"Venue: {props['venue']}")
        
        return "\n".join(parts)

