"""Service for graph operations and relationship linking."""
import logging
from typing import List, Dict, Any
from agents.relationship_linking_agent import RelationshipLinkingAgent
from db.repository import GraphRepository
from graph.models import Edge
from uuid import UUID

logger = logging.getLogger(__name__)


class GraphService:
    """Service for graph operations and cross-paper relationship inference."""
    
    def __init__(
        self,
        relationship_agent: RelationshipLinkingAgent,
        repository: GraphRepository
    ):
        """Initialize graph service."""
        self.relationship_agent = relationship_agent
        self.repository = repository
    
    def link_cross_paper_relationships(self) -> int:
        """
        Infer and create cross-paper relationships.
        
        Returns:
            Number of relationships created
        """
        logger.info("Linking cross-paper relationships")
        
        # Get all papers
        papers = self.repository.get_all_papers()
        if len(papers) < 2:
            logger.info("Need at least 2 papers to infer relationships")
            return 0
        
        
        # Convert to node format
        paper_nodes = []
        for paper in papers:
            node = self.repository.get_node_supabase(paper["node_id"])
            if node:
                paper_nodes.append(node)
        
        # Get concepts and methods for context
        concepts = self.repository.get_all_nodes_by_type("concept")
        methods = self.repository.get_all_nodes_by_type("method")
        
        # Infer relationships
        edges = self.relationship_agent.infer_relationships(
            paper_nodes,
            concepts,
            methods
        )
        
        # Store edges
        edges_created = 0
        for edge in edges:
            try:
                self.repository.create_edge(edge)
                edges_created += 1
            except Exception as e:
                logger.warning(f"Failed to create edge when creating link cross paper relationship: {e}")
        
        logger.info(f"Created {edges_created} cross-paper relationships")
        return edges_created
    
    def link_cross_paper_relationships_pruned(
        self,
        k_neighbors: int = 10,
        min_similarity: float = 0.0
    ) -> int:
        """
        Infer and create cross-paper relationships, but only between papers that:
          1) are semantically similar (top-k neighbors per paper)
          2) share at least one dataset node

        This prunes the candidate pairs heavily.
        """
        logger.info("Linking cross-paper relationships with semantic + dataset pruning")

        papers = self.repository.get_all_papers()
        if len(papers) < 2:
            logger.info("Need at least 2 papers to infer relationships")
            return 0

        # Preload paper nodes and dataset sets
        paper_nodes: Dict[UUID, Dict[str, Any]] = {}
        paper_datasets: Dict[UUID, set[UUID]] = {}

        for p in papers:
            node_id = UUID(str(p["node_id"]))
            node = self.repository.get_node_supabase(node_id)
            if not node:
                continue
            paper_nodes[node_id] = node
            paper_datasets[node_id] = self.repository.get_paper_dataset_ids(node_id)

        # If you want concept/method context for the LLM:
        concepts = self.repository.get_all_nodes_by_type("concept")
        methods = self.repository.get_all_nodes_by_type("method")

        seen_pairs: set[tuple[str, str]] = set()
        edges_created = 0

        for p in papers:
            src_id = UUID(str(p["node_id"]))
            src_node = paper_nodes.get(src_id)
            if not src_node:
                continue

            src_datasets = paper_datasets.get(src_id, set())
            if not src_datasets:
                # No datasets → skip if you only care about dataset-linked relations
                continue
            # import ipdb; ipdb.set_trace()
            # Step 1: semantic neighbors
            neighbors = self.repository.get_similar_papers_for_node(
                src_id,
                k=k_neighbors,
            )
            # import ipdb; ipdb.set_trace()
            for nb in neighbors:
                dst_id = UUID(str(nb["node_id"]))
                if dst_id == src_id:
                    continue

                # De-duplicate unordered pairs
                key = tuple(sorted([str(src_id), str(dst_id)]))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)

                # Step 2: shared dataset filter
                dst_datasets = paper_datasets.get(dst_id, set())
                if not dst_datasets:
                    continue

                if not (src_datasets & dst_datasets):
                    # No shared datasets → skip this pair
                    continue

                dst_node = paper_nodes.get(dst_id)
                if not dst_node:
                    continue

                # Step 3: call the LLM only for these pruned pairs
                relationships = self.relationship_agent._compare_papers(
                    src_node,
                    dst_node,
                    concepts,
                    methods,
                )

                for edge in relationships:
                    try:
                        self.repository.create_edge(edge)
                        edges_created += 1
                    except Exception as e:
                        logger.warning(f"Failed to create edge: {e}")

        logger.info(f"Created {edges_created} cross-paper relationships")
        return edges_created
    
    def link_cross_paper_relationships_pruned_2(self) -> int:
        """
        Infer and create cross-paper relationships, but only between papers that:
          1) share at least one dataset node, OR
          2) share at least one method node, OR
          3) share at least one concept node

        This prunes the candidate pairs by finding papers connected through common nodes,
        without using semantic search.
        """
        logger.info("Linking cross-paper relationships with dataset/method/concept node filtering")

        papers = self.repository.get_all_papers()
        if len(papers) < 2:
            logger.info("Need at least 2 papers to infer relationships")
            return 0

        # Preload paper nodes and their connected nodes
        paper_nodes: Dict[UUID, Dict[str, Any]] = {}
        paper_datasets: Dict[UUID, set[UUID]] = {}
        paper_methods: Dict[UUID, set[UUID]] = {}
        paper_concepts: Dict[UUID, set[UUID]] = {}

        for p in papers:
            node_id = UUID(str(p["node_id"]))
            node = self.repository.get_node_supabase(node_id)
            if not node:
                continue
            paper_nodes[node_id] = node
            paper_datasets[node_id] = self.repository.get_paper_dataset_ids(node_id)
            paper_methods[node_id] = self.repository.get_paper_method_ids(node_id)
            paper_concepts[node_id] = self.repository.get_paper_concept_ids(node_id)

        # If you want concept/method context for the LLM:
        concepts = self.repository.get_all_nodes_by_type("concept")
        methods = self.repository.get_all_nodes_by_type("method")

        seen_pairs: set[tuple[str, str]] = set()
        edges_created = 0

        # Build a map from node (dataset/method/concept) to papers connected to it
        node_to_papers: Dict[UUID, set[UUID]] = {}
        
        # Index all papers by their connected nodes
        for paper_id in paper_nodes.keys():
            # Add to dataset index
            for dataset_id in paper_datasets.get(paper_id, set()):
                if dataset_id not in node_to_papers:
                    node_to_papers[dataset_id] = set()
                node_to_papers[dataset_id].add(paper_id)
            
            # Add to method index
            for method_id in paper_methods.get(paper_id, set()):
                if method_id not in node_to_papers:
                    node_to_papers[method_id] = set()
                node_to_papers[method_id].add(paper_id)
            
            # Add to concept index
            for concept_id in paper_concepts.get(paper_id, set()):
                if concept_id not in node_to_papers:
                    node_to_papers[concept_id] = set()
                node_to_papers[concept_id].add(paper_id)

        # Now find pairs of papers that share at least one common node
        for paper_id in paper_nodes.keys():
            src_node = paper_nodes.get(paper_id)
            if not src_node:
                continue

            # Get all connected nodes for this paper
            all_connected_nodes = (
                paper_datasets.get(paper_id, set()) |
                paper_methods.get(paper_id, set()) |
                paper_concepts.get(paper_id, set())
            )

            if not all_connected_nodes:
                # Skip papers with no connections
                continue

            # Find candidate papers through shared nodes
            candidate_papers: set[UUID] = set()
            for connected_node_id in all_connected_nodes:
                papers_connected_to_node = node_to_papers.get(connected_node_id, set())
                # Add all papers connected to this node (excluding self)
                candidate_papers.update(papers_connected_to_node)
            
            # Remove self
            candidate_papers.discard(paper_id)

            # Process each candidate pair
            for dst_id in candidate_papers:
                if dst_id == paper_id:
                    continue

                # De-duplicate unordered pairs
                key = tuple(sorted([str(paper_id), str(dst_id)]))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)

                # Check if they share at least one common node
                dst_datasets = paper_datasets.get(dst_id, set())
                dst_methods = paper_methods.get(dst_id, set())
                dst_concepts = paper_concepts.get(dst_id, set())

                src_datasets = paper_datasets.get(paper_id, set())
                src_methods = paper_methods.get(paper_id, set())
                src_concepts = paper_concepts.get(paper_id, set())

                # Check for shared nodes
                shared_datasets = src_datasets & dst_datasets
                shared_methods = src_methods & dst_methods
                shared_concepts = src_concepts & dst_concepts

                if not (shared_datasets or shared_methods or shared_concepts):
                    # No shared nodes → skip this pair
                    continue

                dst_node = paper_nodes.get(dst_id)
                if not dst_node:
                    continue
                # import ipdb; ipdb.set_trace()
                # Call the LLM for these pruned pairs
                if shared_datasets:
                    print(f'found shared dataset {src_datasets} between {src_datasets} {src_methods}')
                if shared_methods:
                    print(f'found shared method {shared_methods} between {src_methods} and {dst_methods}')
                if shared_concepts:
                    print(f'found shared concept {shared_concepts} between {src_concepts} and {dst_concepts}')

                relationships = self.relationship_agent._compare_papers(
                    src_node,
                    dst_node,
                    concepts,
                    methods,
                )

                logger.info(f'found {len(relationships)} relationships, creating edges')
                if len(relationships)==0:
                    import ipdb; ipdb.set_trace()
                for edge in relationships:
                    try:
                        self.repository.create_edge(edge)
                        edges_created += 1
                    except Exception as e:
                        logger.warning(f"Failed to create edge: {e}")

        logger.info(f"Created {edges_created} cross-paper relationships")
        return edges_created
    
    def get_paper_improvements(self, paper_node_id: str) -> List[dict]:
        """
        Get papers that improve on a given paper.
        
        Args:
            paper_node_id: UUID of the paper node
        
        Returns:
            List of papers that improve on the given paper
        """
        from uuid import UUID
        edges = self.repository.get_edges_to_node(UUID(paper_node_id), "IMPROVES_ON")
        
        improvements = []
        for edge in edges:
            paper = self.repository.get_node_supabase(edge["from_node_id"])
            if paper:
                improvements.append({
                    "paper": paper,
                    "edge": edge
                })
        
        return improvements
    
    def get_paper_concepts(self, paper_node_id: str) -> List[dict]:
        """
        Get concepts introduced by a paper.
        
        Args:
            paper_node_id: UUID of the paper node
        
        Returns:
            List of concepts introduced by the paper
        """
        from uuid import UUID
        edges = self.repository.get_edges_from_node(UUID(paper_node_id), "INTRODUCES")
        
        concepts = []
        for edge in edges:
            concept = self.repository.get_node_supabase(edge["to_node_id"])
            if concept and concept.get("node_type") == "concept":
                concepts.append({
                    "concept": concept,
                    "edge": edge
                })
        
        return concepts
    
    def get_paper_datasets(self, paper_node_id: str) -> List[dict]:
        """
        Get datasets used or evaluated on by a paper.

        Returns:
            List of dataset nodes + edges.
        """
        from uuid import UUID
        edges = self.repository.get_edges_from_node(UUID(paper_node_id), None)

        datasets = []
        for edge in edges:
            if edge["edge_type"] in ("USES_DATASET", "EVALUATES_ON"):
                node = self.repository.get_node_supabase(edge["to_node_id"])
                if node and node.get("node_type") == "dataset":
                    datasets.append({"dataset": node, "edge": edge})
        return datasets

    def get_paper_metrics(self, paper_node_id: str) -> List[dict]:
        """
        Get metrics used for evaluation in a paper.
        """
        from uuid import UUID
        edges = self.repository.get_edges_from_node(UUID(paper_node_id), "EVALUATES_WITH")

        metrics = []
        for edge in edges:
            metric = self.repository.get_node_supabase(edge["to_node_id"])
            if metric and metric.get("node_type") == "metric":
                metrics.append({"metric": metric, "edge": edge})
        return metrics

    def semantic_search_papers(self, query_text: str, k: int = 5) -> List[Dict[str, Any]]:
        llm = self.relationship_agent.llm
        embedding = llm.embed(query_text)
        return self.repository.search_similar_papers(embedding, k)
    
    def get_similar_papers(self, paper_node_id: str) -> List[dict]:
        """
        Get papers that are similar to a given paper (connected via SIMILAR_TO edges).
        
        Args:
            paper_node_id: UUID of the paper node
        
        Returns:
            List of papers that are similar to the given paper
        """
        from uuid import UUID
        paper_uuid = UUID(paper_node_id)
        
        # Get SIMILAR_TO edges where this paper is the source (from_node)
        edges_from = self.repository.get_edges_from_node(paper_uuid, "SIMILAR_TO")
        
        # Get SIMILAR_TO edges where this paper is the target (to_node)
        edges_to = self.repository.get_edges_to_node(paper_uuid, "SIMILAR_TO")
        
        # Combine both directions
        all_edges = edges_from + edges_to
        
        similar_papers = []
        seen_paper_ids = set()
        
        for edge in all_edges:
            # Normalize edge IDs to UUID for comparison
            from_id = edge["from_node_id"]
            to_id = edge["to_node_id"]
            
            # Convert to UUID if they're strings
            if isinstance(from_id, str):
                from_id = UUID(from_id)
            if isinstance(to_id, str):
                to_id = UUID(to_id)
            
            # Determine which node is the similar paper (not the input paper)
            if from_id == paper_uuid:
                similar_paper_id = to_id
            else:
                similar_paper_id = from_id
            
            # Avoid duplicates
            if similar_paper_id in seen_paper_ids:
                continue
            seen_paper_ids.add(similar_paper_id)
            
            # Get the similar paper node
            paper = self.repository.get_node_supabase(similar_paper_id)
            if paper:
                similar_papers.append({
                    "paper": paper,
                    "edge": edge
                })
        
        return similar_papers


    

