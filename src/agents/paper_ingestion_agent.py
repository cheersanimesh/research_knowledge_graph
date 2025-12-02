"""Agent for ingesting and processing paper content."""
import logging
from typing import Dict, Any, Optional
from utils.llm import LLMClient
from utils.pdf import load_text_from_file

logger = logging.getLogger(__name__)


class PaperIngestionAgent:
    """Agent responsible for ingesting papers and extracting metadata."""
    
    def __init__(self, llm_client: LLMClient):
        """Initialize ingestion agent."""
        self.llm = llm_client
    
    def ingest_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        Ingest a paper from a file path.
        
        Args:
            file_path: Path to PDF or text file
        
        Returns:
            Dictionary with paper metadata and text chunks
        """
        logger.info(f"Ingesting paper from file: {file_path}")
        text = load_text_from_file(file_path)
        
        if not text:
            raise ValueError(f"Could not extract text from {file_path}")
        
        return self.ingest_from_text(text, source_file=file_path)
    
    def ingest_from_text(self, text: str, source_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Ingest a paper from raw text.
        
        Args:
            text: Paper text content
            source_file: Optional source file path
        
        Returns:
            Dictionary with paper metadata and text chunks
        """
        # Extract metadata using LLM
        metadata = self._extract_metadata(text)
        
        # Split into chunks (simple approach - can be enhanced)
        chunks = self._chunk_text(text, chunk_size=2000)
        
        return {
            "metadata": metadata,
            "text_chunks": chunks,
            "full_text": text,
            "source_file": source_file
        }
    
    def ingest_from_dict(self, paper_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingest a paper from a dictionary (e.g., from JSON).
        
        Args:
            paper_dict: Dictionary with paper data
        
        Returns:
            Dictionary with paper metadata and text chunks
        """
        # If text is provided, use it; otherwise try to construct from fields
        text = paper_dict.get("text") or paper_dict.get("content")
        
        if not text:
            # Construct text from available fields
            text_parts = []
            if paper_dict.get("title"):
                text_parts.append(f"Title: {paper_dict['title']}")
            if paper_dict.get("abstract"):
                text_parts.append(f"Abstract: {paper_dict['abstract']}")
            if paper_dict.get("body"):
                text_parts.append(paper_dict["body"])
            text = "\n\n".join(text_parts)
        
        result = self.ingest_from_text(text)
        
        # Merge provided metadata
        if paper_dict.get("title"):
            result["metadata"]["title"] = paper_dict["title"]
        if paper_dict.get("abstract"):
            result["metadata"]["abstract"] = paper_dict["abstract"]
        if paper_dict.get("year"):
            result["metadata"]["year"] = paper_dict["year"]
        if paper_dict.get("venue"):
            result["metadata"]["venue"] = paper_dict["venue"]
        if paper_dict.get("doi"):
            result["metadata"]["doi"] = paper_dict["doi"]
        if paper_dict.get("arxiv_id"):
            result["metadata"]["arxiv_id"] = paper_dict["arxiv_id"]
        if paper_dict.get("authors"):
            result["metadata"]["authors"] = paper_dict["authors"]
        
        return result
    
    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        """Extract paper metadata using LLM."""
        system_prompt = """You are an expert at extracting comprehensive metadata from academic papers.
Extract the following information if available:
- title
- abstract (if not already provided)
- year
- venue (conference/journal name)
- doi
- arxiv_id
- authors (list of author names)
- citation_count (if mentioned)
- methods: List of methods/algorithms used or introduced in the paper, including:
  - method_name: Name of the method/algorithm
  - description: Brief description
  - key_components: Key components or steps
  - parameters: Important parameters or hyperparameters mentioned
  - complexity: Computational complexity if mentioned
  - implementation_details: Notable implementation details
- metrics: List of evaluation metrics used or reported, including:
  - metric_name: Name of the metric
  - description: What it measures
  - reported_values: Any specific values reported for this metric
  - benchmarks: Baseline or comparison values if mentioned
  - datasets_used: Which datasets this metric was computed on
- experimental_setup: Summary of experimental setup including:
  - hardware: Hardware used (GPU models, number of GPUs, etc.)
  - software: Software frameworks and versions
  - datasets: List of datasets used
  - evaluation_protocol: How experiments were conducted
- key_results: Summary of key experimental results and findings
- limitations: Limitations or weaknesses mentioned in the paper
- future_work: Future work or directions mentioned
- code_availability: Whether code is available (GitHub link, repository URL)
- data_availability: Whether data/datasets are available
- supplementary_materials: Link to supplementary materials if mentioned
- keywords: Keywords or subject areas

Return a JSON object with these fields. Use null for missing fields. For methods and metrics, return arrays of objects with the detailed properties. For experimental_setup and key_results, provide concise summaries."""
        
        user_prompt = f"""Extract comprehensive metadata from the following paper text:

{text[:10000]}  # Increased to 10000 chars to capture more metadata

Return JSON with fields: title, abstract, year, venue, doi, arxiv_id, authors (array), citation_count, methods (array), metrics (array), experimental_setup (object with hardware, software, datasets, evaluation_protocol), key_results (string summary), limitations (string or array), future_work (string or array), code_availability (string URL), data_availability (string), supplementary_materials (string URL), keywords (array).

Pay special attention to:
1. Extracting detailed information about methods and metrics used in the paper
2. Capturing experimental setup details from methodology and experiments sections
3. Summarizing key results from results/discussion sections
4. Extracting limitations and future work from conclusion/future work sections
5. Finding code/data availability information"""
        
        try:
            metadata = self.llm.complete_json(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=15000  # Increased to handle comprehensive metadata
            )
            return metadata
        except Exception as e:
            logger.warning(f"Failed to extract metadata via LLM: {e}, using defaults")
            return {
                "title": "Unknown",
                "abstract": text if text else "",
                "year": None,
                "venue": None,
                "doi": None,
                "arxiv_id": None,
                "authors": [],
                "citation_count": None,
                "methods": [],
                "metrics": [],
                "experimental_setup": None,
                "key_results": None,
                "limitations": None,
                "future_work": None,
                "code_availability": None,
                "data_availability": None,
                "supplementary_materials": None,
                "keywords": []
            }
    
    def _chunk_text(self, text: str, chunk_size: int = 2000, overlap: int = 200) -> list:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full text
            chunk_size: Size of each chunk
            overlap: Overlap between chunks
        
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)
                if break_point > chunk_size * 0.7:  # Only break if we're not too early
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1
            
            chunks.append(chunk.strip())
            start = end - overlap
        
        return chunks

