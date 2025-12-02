"""Agent for extracting entities and relationships from papers."""
import json
import logging
from operator import itemgetter
from typing import List, Dict, Any
from utils.llm import LLMClient
from config import Config
from graph.models import (
    EntityExtractionResult,
    ExtractedEntity,
    ExtractedRelationship
)

logger = logging.getLogger(__name__)


class EntityExtractionAgent:
    """Agent responsible for extracting entities and relationships from paper text."""
    
    def __init__(self, llm_client: LLMClient):
        """Initialize entity extraction agent."""
        self.llm = llm_client
    
    def extract_entities(self, paper_text: str, paper_title: str = "") -> EntityExtractionResult:
        """
        Extract entities and relationships from paper text.
        
        Args:
            paper_text: Full text of the paper
            paper_title: Title of the paper (for context)
        
        Returns:
            EntityExtractionResult with all extracted entities and relationships
        """
        logger.info(f"Extracting entities from paper: {paper_title}")
        
        # Use LLM to extract entities
        extraction_result = self._extract_with_llm(paper_text, paper_title)
        
        return extraction_result
    
    def _extract_with_llm(self, text: str, title: str) -> EntityExtractionResult:
        """Use LLM to extract entities and relationships."""
        # Check if debug mode is enabled
        if Config.DEBUG:
            logger.info("DEBUG mode: Returning default extraction result (skipping LLM call)")
            # import ipdb; ipdb.set_trace()
            return self._get_default_extraction_result(title)
        
        system_prompt = """You are an expert at extracting structured information from academic papers.
Extract the following:

1. CONCEPTS: Key concepts, ideas, or theoretical contributions
2. METHODS: Technical methods, algorithms, or approaches
   For each METHOD, extract comprehensive properties including:
   - algorithm_type: Type of algorithm (e.g., "optimization", "neural network", "graph algorithm")
   - key_components: List of key components or steps with detailed descriptions
   - parameters: Dictionary of important parameters/hyperparameters with their values/ranges
   - computational_complexity: Time/space complexity if mentioned (with notation)
   - implementation_details: Notable implementation details (frameworks, libraries, tools used)
   - hardware_requirements: GPU/TPU requirements, memory needs, compute specifications
   - software_dependencies: Required software, libraries, frameworks, versions
   - code_availability: Whether code is available (GitHub link, repository, etc.)
   - training_details: Training procedure, epochs, batch size, optimization details
   - inference_details: Inference time, latency, throughput if mentioned
   - dependencies: Dependencies on other methods or concepts
   - variants: Any variants or extensions mentioned
   - advantages: Key advantages or strengths of the method
   - limitations: Limitations or weaknesses mentioned
3. DATASETS: Datasets used or mentioned
   For each DATASET, extract properties including:
   - dataset_type: Type of dataset (e.g., "image", "video", "3D", "synthetic")
   - size: Number of samples, images, scenes, etc.
   - domain: Application domain (e.g., "medical imaging", "autonomous driving")
   - license: License information if mentioned
   - download_link: URL or reference if available
   - usage: How the dataset is used (training, evaluation, comparison)
4. METRICS: Evaluation metrics or performance measures
   For each METRIC, extract comprehensive properties including:
   - metric_type: Type of metric (e.g., "accuracy", "quality", "efficiency", "robustness")
   - reported_values: Dictionary mapping dataset/task to reported value (include standard deviations if mentioned)
   - baseline_values: Comparison values with baselines/methods (with method names)
   - units: Units of measurement
   - significance: Statistical significance, p-values, confidence intervals if mentioned
   - experimental_setup: Detailed conditions under which metric was measured
   - hardware_used: Hardware used for evaluation (GPU model, number of GPUs, etc.)
   - evaluation_protocol: Evaluation protocol, splits, cross-validation details
   - comparison_methods: List of methods compared against
   - ablation_study_results: Results from ablation studies if mentioned
5. AUTHORS: Author names (if not already in metadata)
6. TASKS: Tasks or problem settings the paper addresses (e.g., "novel view synthesis", "dynamic scene reconstruction")
7. RELATIONSHIPS: Intra-paper relationships such as:
   - INTRODUCES: Paper introduces a concept/method
   - USES_CONCEPT: Paper uses a concept
   - USES_DATASET: Paper uses/evaluates on a dataset
   - EVALUATES_WITH: Paper evaluates using a metric
   - EVALUATES_ON: Paper evaluates on a dataset
   - IMPROVES_ON: Method improves upon another method
   - COMPARES_WITH: Method is compared with another method

For each entity, provide:
- label: The name/identifier
- description: Brief but comprehensive description
- properties: Additional metadata (should be detailed for methods, metrics, and datasets)

For each relationship, provide:
- from_entity_label: Source entity
- to_entity_label: Target entity
- relationship_type: Type of relationship
- confidence: Confidence score (0.0-1.0)
- rationale: Brief explanation
- evidence_span: Section or location in paper

Return a JSON object with this structure:
{
  "concepts": [{"entity_type": "concept", "label": "...", "description": "...", "properties": {}}],
  "methods": [{"entity_type": "method", "label": "...", "description": "...", "properties": {"algorithm_type": "...", "key_components": [...], "parameters": {...}, "hardware_requirements": "...", "software_dependencies": [...], "code_availability": "...", "training_details": {...}, ...}}],
  "datasets": [{"entity_type": "dataset", "label": "...", "description": "...", "properties": {"dataset_type": "...", "size": "...", "domain": "...", "usage": "..."}}],
  "metrics": [{"entity_type": "metric", "label": "...", "description": "...", "properties": {"metric_type": "...", "reported_values": {...}, "baseline_values": {...}, "experimental_setup": "...", "hardware_used": "...", "evaluation_protocol": "...", "comparison_methods": [...], ...}}],
  "authors": [{"entity_type": "author", "label": "...", "description": "...", "properties": {}}],
  "relationships": [{"from_entity_label": "...", "to_entity_label": "...", "relationship_type": "...", "confidence": 0.9, "rationale": "...", "evidence_span": "..."}],
  "tasks": [{"entity_type": "task", "label": "...", "description": "...", "properties": {}}]
}"""
        
        # Use larger text sample for detailed extraction (methods/metrics often in methodology/results sections)
        # Use first 15000 chars to capture more of the paper including methodology, results, and experiments sections
        text_sample = text[:15000] if len(text) > 15000 else text
        
        user_prompt = f"""Extract entities and relationships from this academic paper:

Title: {title}

Text:
{text_sample}

Extract all relevant entities (concepts, methods, datasets, metrics, authors, tasks) and their relationships.

IMPORTANT: For METHODS, extract comprehensive properties including:
- Algorithm type, key components, and step-by-step procedure
- Parameters and hyperparameters with their specific values or ranges
- Computational complexity (time and space)
- Implementation details (frameworks, libraries, tools)
- Hardware requirements (GPU models, memory, compute)
- Software dependencies and versions
- Code availability (GitHub links, repositories)
- Training details (epochs, batch size, optimizer, learning rate schedule)
- Inference details (latency, throughput, real-time performance)
- Advantages and limitations

IMPORTANT: For METRICS, extract comprehensive properties including:
- Reported values for each dataset/task (include standard deviations if available)
- Baseline/comparison values with method names
- Units of measurement
- Statistical significance (p-values, confidence intervals)
- Detailed experimental setup and conditions
- Hardware used for evaluation
- Evaluation protocol and data splits
- List of methods compared against
- Ablation study results if mentioned

IMPORTANT: For DATASETS, extract properties including:
- Dataset type and domain
- Size and scale
- License information
- Usage context (training/evaluation)

Extract as much detail as possible from the methodology, experiments, and results sections."""
        
        try:
            result_json = self.llm.complete_json(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=12000  # Increased to handle comprehensive detailed properties
            )
            
            # Parse and validate
            return self._parse_extraction_result(result_json)
        except Exception as e:
            logger.error(f"Failed to extract entities via LLM: {e}")
            # Return empty result on error
            return EntityExtractionResult()
    
    def _get_default_extraction_result(self, title: str) -> EntityExtractionResult:
        """Return default extraction result for debug mode."""
        return EntityExtractionResult(
            concepts=[
                ExtractedEntity(
                    entity_type="concept",
                    label="3D Gaussian Splatting",
                    description="A method for novel view synthesis using 3D Gaussian primitives",
                    properties={}
                ),
                ExtractedEntity(
                    entity_type="concept",
                    label="Neural Rendering",
                    description="Rendering techniques using neural networks",
                    properties={}
                )
            ],
            methods=[
                ExtractedEntity(
                    entity_type="method",
                    label="Gaussian Splatting Algorithm",
                    description="Algorithm for rendering 3D scenes using Gaussian primitives",
                    properties={
                        "algorithm_type": "neural rendering",
                        "key_components": ["3D Gaussian primitives", "splatting", "differentiable rasterization"],
                        "parameters": {
                            "learning_rate": 0.001,
                            "densification_interval": 100
                        },
                        "computational_complexity": "O(n) where n is number of Gaussians",
                        "implementation_details": "Uses CUDA for efficient rasterization",
                        "hardware_requirements": "NVIDIA GPU with CUDA support, 24GB VRAM",
                        "software_dependencies": ["PyTorch", "CUDA toolkit", "OpenGL"],
                        "code_availability": "https://github.com/graphdeco-inria/gaussian-splatting",
                        "training_details": {
                            "epochs": 30000,
                            "batch_size": 1,
                            "optimizer": "Adam"
                        },
                        "inference_details": "Real-time rendering at 60 FPS",
                        "advantages": "High-quality rendering with real-time performance",
                        "limitations": "Requires significant GPU memory"
                    }
                )
            ],
            datasets=[
                ExtractedEntity(
                    entity_type="dataset",
                    label="Mip-NeRF 360",
                    description="Dataset for novel view synthesis evaluation",
                    properties={
                        "dataset_type": "3D scenes",
                        "size": "9 scenes",
                        "domain": "computer vision",
                        "usage": "evaluation",
                        "download_link": "https://jonbarron.info/mipnerf360/"
                    }
                )
            ],
            metrics=[
                ExtractedEntity(
                    entity_type="metric",
                    label="PSNR",
                    description="Peak Signal-to-Noise Ratio for image quality evaluation",
                    properties={
                        "metric_type": "quality",
                        "reported_values": {
                            "Mip-NeRF 360": {"mean": 27.21, "std": 0.5},
                            "Tanks and Temples": {"mean": 26.54, "std": 0.3}
                        },
                        "baseline_values": {
                            "NeRF": 25.78,
                            "Mip-NeRF": 26.52
                        },
                        "units": "dB",
                        "experimental_setup": "Novel view synthesis task, evaluated on held-out test views",
                        "hardware_used": "NVIDIA RTX 3090",
                        "evaluation_protocol": "Standard train/test split, 8:2 ratio",
                        "comparison_methods": ["NeRF", "Mip-NeRF", "Plenoxels"],
                        "significance": "Statistically significant improvement (p < 0.01)"
                    }
                ),
                ExtractedEntity(
                    entity_type="metric",
                    label="SSIM",
                    description="Structural Similarity Index for image quality evaluation",
                    properties={
                        "metric_type": "quality",
                        "reported_values": {
                            "Mip-NeRF 360": {"mean": 0.815, "std": 0.02}
                        },
                        "baseline_values": {
                            "NeRF": 0.792,
                            "Mip-NeRF": 0.810
                        },
                        "units": "score (0-1)",
                        "experimental_setup": "Novel view synthesis task, evaluated on held-out test views",
                        "hardware_used": "NVIDIA RTX 3090",
                        "evaluation_protocol": "Standard train/test split, 8:2 ratio",
                        "comparison_methods": ["NeRF", "Mip-NeRF", "Plenoxels"]
                    }
                )
            ],
            authors=[],
            relationships=[
                ExtractedRelationship(
                    from_entity_label=title or "Paper",
                    to_entity_label="3D Gaussian Splatting",
                    relationship_type="INTRODUCES",
                    confidence=0.9,
                    rationale="Paper introduces the 3D Gaussian Splatting method",
                    evidence_span="Introduction and Methodology sections"
                ),
                ExtractedRelationship(
                    from_entity_label="Gaussian Splatting Algorithm",
                    to_entity_label="Mip-NeRF 360",
                    relationship_type="EVALUATES_ON",
                    confidence=0.85,
                    rationale="Method is evaluated on the Mip-NeRF 360 dataset",
                    evidence_span="Experiments section"
                ),
                ExtractedRelationship(
                    from_entity_label="Gaussian Splatting Algorithm",
                    to_entity_label="PSNR",
                    relationship_type="EVALUATES_WITH",
                    confidence=0.9,
                    rationale="Method is evaluated using PSNR metric",
                    evidence_span="Results section"
                )
            ]
        )
    
    def _parse_extraction_result(self, result_json: Dict[str, Any]) -> EntityExtractionResult:
        """Parse and validate LLM extraction result."""
        try:
            concepts = [
                ExtractedEntity(**item) if isinstance(item, dict) else item
                for item in result_json.get("concepts", [])
            ]
            methods = [
                ExtractedEntity(**item) if isinstance(item, dict) else item
                for item in result_json.get("methods", [])
            ]
            datasets = [
                ExtractedEntity(**item) if isinstance(item, dict) else item
                for item in result_json.get("datasets", [])
            ]
            metrics = [
                ExtractedEntity(**item) if isinstance(item, dict) else item
                for item in result_json.get("metrics", [])
            ]
            authors = [
                ExtractedEntity(**item) if isinstance(item, dict) else item
                for item in result_json.get("authors", [])
            ]
            relationships = [
                ExtractedRelationship(**item) if isinstance(item, dict) else item
                for item in result_json.get("relationships", [])
            ]
            tasks = [
                ExtractedEntity(**item) if isinstance(item, dict) else item
                for item in result_json.get("tasks", [])
            ]
            
            return EntityExtractionResult(
                concepts=concepts,
                methods=methods,
                datasets=datasets,
                metrics=metrics,
                authors=authors,
                tasks = tasks,
                relationships=relationships
            )
        except Exception as e:
            logger.error(f"Failed to parse extraction result: {e}")
            logger.error(f"Result JSON: {json.dumps(result_json, indent=2)}")
            return EntityExtractionResult()

