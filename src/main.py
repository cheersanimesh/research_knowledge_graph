"""Main CLI entrypoint for the paper graph system."""
import json
import logging
import sys
from pathlib import Path
from typing import Optional
from services import qa_service
import typer
from config import Config
from db.client import DatabaseClient
from db.repository import GraphRepository
from utils.llm import LLMClient
from agents.paper_ingestion_agent import PaperIngestionAgent
from agents.entity_extraction_agent import EntityExtractionAgent
from agents.relationship_linking_agent import RelationshipLinkingAgent
from agents.validation_agent import ValidationAgent
from services.ingestion_service import IngestionService
from services.graph_service import GraphService
from services.qa_service import QAService
from services.graph_visualizer import GraphVisualizer
# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = typer.Typer(help="Paper Graph Knowledge System CLI")


def _initialize_services():
    """Initialize all services and agents."""
    Config.validate()
    
    # Initialize database
    db_client = DatabaseClient()
    repository = GraphRepository(db_client)
    
    # Initialize LLM
    llm_client = LLMClient()
    
    # Initialize agents
    ingestion_agent = PaperIngestionAgent(llm_client)
    extraction_agent = EntityExtractionAgent(llm_client)
    relationship_agent = RelationshipLinkingAgent(llm_client)
    validation_agent = ValidationAgent()
    
    # Initialize services
    ingestion_service = IngestionService(
        ingestion_agent,
        extraction_agent,
        validation_agent,
        repository
    )
    
    graph_service = GraphService(relationship_agent, repository)
    
    qa_service = QAService(graph_service= graph_service, llm_client= llm_client)
    return {
        "db_client": db_client,
        "repository": repository,
        "ingestion_service": ingestion_service,
        "graph_service": graph_service,
        'qa_service': qa_service
    }


@app.command()
def ingest(
    input_path: str = typer.Argument(..., help="Path to JSON file, PDF file, or directory containing JSON/PDF files"),
    link_relationships: bool = typer.Option(True, "--link/--no-link", help="Link cross-paper relationships after ingestion")
):
    """Ingest papers from a JSON file, PDF file, or directory containing JSON/PDF files."""
    logger.info(f"Starting ingestion from: {input_path}")
    
    services = _initialize_services()
    ingestion_service = services["ingestion_service"]
    graph_service = services["graph_service"]
    db_client = services["db_client"]

    # edges_created = graph_service.link_cross_paper_relationships_pruned_2()
    # typer.echo(f"  ✓ Created {edges_created} cross-paper relationships")

    # exit(0)

    try:
        input_path_obj = Path(input_path)
        
        # Load papers
        if input_path_obj.is_file():
            if input_path_obj.suffix == '.json':
                with open(input_path_obj, 'r') as f:
                    papers_data = json.load(f)
                if not isinstance(papers_data, list):
                    papers_data = [papers_data]
            else:
                # Assume it's a single paper file
                papers_data = [{"file_path": str(input_path_obj)}]
        elif input_path_obj.is_dir():
            # Load all JSON and PDF files in directory
            json_files = list(input_path_obj.glob("*.json"))
            pdf_files = list(input_path_obj.glob("*.pdf"))
            papers_data = []
            
            # Process JSON files
            for json_file in json_files:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        papers_data.extend(data)
                    else:
                        papers_data.append(data)
            
            # Process PDF files
            for pdf_file in pdf_files:
                papers_data.append({"file_path": str(pdf_file)})
        else:
            typer.echo(f"Error: {input_path} does not exist", err=True)
            sys.exit(1)
        
        # Ingest each paper
        results = []
        # papers_data = papers_data[:2]
        for i, paper_data in enumerate(papers_data, 1):
            typer.echo(f"Processing paper {i}/{len(papers_data)}...")
            try:
                result = ingestion_service.ingest_paper(paper_data)

                results.append(result)
                typer.echo(f"  ✓ Ingested: {result['title']}")
                typer.echo(f"    Entities: {result['entities_created']}, Edges: {result['edges_created']}")
            except Exception as e:
                logger.error(f"Failed to ingest paper {i}: {e}")
                typer.echo(f"  ✗ Failed: {e}", err=True)
        
        # Link cross-paper relationships
        
        if link_relationships and len(results) > 1:
            typer.echo("\nLinking cross-paper relationships...")
            edges_created = graph_service.link_cross_paper_relationships_pruned_2()
            typer.echo(f"  ✓ Created {edges_created} cross-paper relationships")
        
        # Summary
        typer.echo(f"\n{'='*50}")
        typer.echo(f"Ingestion complete!")
        typer.echo(f"Papers processed: {len(results)}")
        typer.echo(f"Successfully ingested: {sum(1 for r in results if 'title' in r)}")
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        db_client.close()


@app.command()
def visualize(
    output: str = typer.Option("graph_visualization.html", "--output", "-o", help="Output HTML file path"),
    node_type: Optional[str] = typer.Option(None, "--node-type", help="Filter by node type (paper, concept, method, dataset, metric, author, task)"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of nodes to visualize"),
    subgraph: Optional[str] = typer.Option(None, "--subgraph", help="Visualize subgraph starting from this node ID"),
    max_depth: int = typer.Option(2, "--max-depth", help="Maximum depth for subgraph visualization"),
    no_physics: bool = typer.Option(False, "--no-physics", help="Disable physics simulation"),
    no_edge_labels: bool = typer.Option(False, "--no-edge-labels", help="Hide edge type labels")
):
    """Visualize the knowledge graph as an interactive HTML file."""
    services = _initialize_services()
    repository = services["repository"]
    db_client = services["db_client"]
    
    try:
        visualizer = GraphVisualizer(repository)
        
        if subgraph:
            from uuid import UUID
            try:
                root_node_id = UUID(subgraph)
                output_path = visualizer.visualize_subgraph(
                    root_node_id,
                    max_depth=max_depth,
                    output_path=output
                )
            except ValueError:
                typer.echo(f"Error: Invalid UUID format: {subgraph}", err=True)
                sys.exit(1)
        else:
            output_path = visualizer.visualize(
                output_path=output,
                node_type_filter=node_type,
                limit=limit,
                physics=not no_physics,
                show_edge_labels=not no_edge_labels
            )
        
        if output_path:
            typer.echo(f"\n✓ Graph visualization saved to: {output_path}")
            typer.echo("  Open this file in your web browser to view the interactive graph.")
        else:
            typer.echo("Error: Failed to create visualization", err=True)
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Visualization failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        db_client.close()


@app.command()
def query(
    query_type: str = typer.Argument(..., help="Query type: improvements, concepts, papers, similar"),
    paper_id: Optional[str] = typer.Option(None, "--paper-id", help="Paper ID for query"),
    query: str = typer.Option(None, "--query", help="user query"),
    output: Optional[str] = typer.Option(None, "--output", help="Output file path (JSON)")
):
    """Query the knowledge graph."""
    services = _initialize_services()
    graph_service = services["graph_service"]
    repository = services["repository"]
    db_client = services["db_client"]
    qa_service = services['qa_service']
    try:
        if query_type == "papers":
            papers = repository.get_all_papers()
            typer.echo(f"\nFound {len(papers)} papers:")
            for paper in papers:
                typer.echo(f"  - {paper.get('title', 'Unknown')} ({paper.get('year', 'N/A')})")
                typer.echo(f"    ID: {paper['node_id']}")
        
        elif query_type == "improvements":
            if not paper_id:
                typer.echo("Error: --paper-id required for improvements query", err=True)
                sys.exit(1)
            improvements = graph_service.get_paper_improvements(paper_id)
            typer.echo(f"\nFound {len(improvements)} papers that improve on this paper:")
            for imp in improvements:
                paper = imp["paper"]
                edge = imp["edge"]
                typer.echo(f"  - {paper.get('label', 'Unknown')}")
                typer.echo(f"    Confidence: {edge.get('confidence', 0):.2f}")
                typer.echo(f"    Rationale: {edge.get('properties', {}).get('rationale', 'N/A')}")
        
        elif query_type == "concepts":
            if not paper_id:
                typer.echo("Error: --paper-id required for concepts query", err=True)
                sys.exit(1)
            concepts = graph_service.get_paper_concepts(paper_id)
            typer.echo(f"\nFound {len(concepts)} concepts introduced by this paper:")
            for concept_data in concepts:
                concept = concept_data["concept"]
                typer.echo(f"  - {concept.get('label', 'Unknown')}")
                props = concept.get('properties', {})
                if props.get('description'):
                    typer.echo(f"    {props['description'][:100]}...")
        elif query_type == 'similar':
            if not paper_id:
                typer.echo("Error: --paper-id required for similar query", err=True)
                sys.exit(1)
            similar_papers = graph_service.get_similar_papers(paper_id)
            typer.echo(f"\nFound {len(similar_papers)} papers similar to this paper:")
            for sim in similar_papers:
                paper = sim["paper"]
                edge = sim["edge"]
                typer.echo(f"  - {paper.get('label', 'Unknown')}")
                typer.echo(f"    ID: {paper.get('id')}")
                typer.echo(f"    Confidence: {edge.get('confidence', 0):.2f}")
                rationale = edge.get('properties', {}).get('rationale', 'N/A')
                if rationale and rationale != 'N/A':
                    typer.echo(f"    Rationale: {rationale[:200]}...")
        elif query_type == 'ask_nl_query':
            if not query:
                typer.echo("Error: --query required for natural language query", err=True)
                sys.exit(1)
            query_output = qa_service.answer_question(query)
            print(query_output)
        else:
            typer.echo(f"Unknown query type: {query_type}", err=True)
            typer.echo("Available types: papers, improvements, concepts, similar")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Query failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        db_client.close()


if __name__ == "__main__":
    app()

