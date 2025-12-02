"""Graph visualization service using pyvis for interactive HTML visualizations."""
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from pathlib import Path

from pyvis.network import Network

from db.repository import GraphRepository

logger = logging.getLogger(__name__)


class GraphVisualizer:
    """Service for visualizing the knowledge graph."""
    
    # Color scheme for different node types
    NODE_COLORS = {
        "paper": "#FF6B6B",      # Red
        "concept": "#4ECDC4",    # Teal
        "method": "#45B7D1",     # Blue
        "dataset": "#FFA07A",    # Light Salmon
        "metric": "#98D8C8",     # Mint
        "author": "#F7DC6F",     # Yellow
        "task": "#BB8FCE",       # Purple
        "default": "#95A5A6"     # Gray
    }
    
    # Edge color based on relationship type
    EDGE_COLORS = {
        "IMPROVES_ON": "#E74C3C",      # Red
        "INTRODUCES": "#3498DB",       # Blue
        "USES_DATASET": "#F39C12",     # Orange
        "EVALUATES_ON": "#9B59B6",     # Purple
        "EVALUATES_WITH": "#1ABC9C",   # Turquoise
        "CITES": "#34495E",             # Dark Gray
        "RELATED_TO": "#95A5A6",        # Light Gray
        "default": "#7F8C8D"            # Gray
    }
    
    def __init__(self, repository: GraphRepository):
        """Initialize graph visualizer with repository."""
        self.repository = repository
    
    def get_all_nodes_and_edges(
        self,
        node_type_filter: Optional[str] = None,
        limit: Optional[int] = None
    ):
    # ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Fetch all nodes and edges from the database.
        
        Args:
            node_type_filter: Optional filter for node types (e.g., "paper", "concept")
            limit: Optional limit on number of nodes to fetch
        
        Returns:
            Tuple of (nodes, edges) lists
        """
        logger.info("Fetching nodes and edges from database")
        
        if node_type_filter:
            nodes = self.repository.get_all_nodes_by_type(node_type_filter)
        else:
            # Get all nodes by fetching each type
            all_node_types = ["paper", "concept", "method", "dataset", "metric", "author", "task"]
            nodes = []
            for node_type in all_node_types:
                nodes.extend(self.repository.get_all_nodes_by_type(node_type))
        
        if limit:
            nodes = nodes[:limit]
        
        # Get all edges for the fetched nodes
        node_ids = {UUID(str(node["id"])) for node in nodes}
        edges = []
        
        # Fetch edges where both nodes are in our node set
        for node in nodes:
            node_id = UUID(str(node["id"]))
            # Get outgoing edges
            outgoing = self.repository.get_edges_from_node(node_id)
            for edge in outgoing:
                if UUID(str(edge["to_node_id"])) in node_ids:
                    edges.append(edge)
        
        logger.info(f"Fetched {len(nodes)} nodes and {len(edges)} edges")
        return nodes, edges
    
    def visualize(
        self,
        output_path: str = "graph_visualization.html",
        node_type_filter: Optional[str] = None,
        limit: Optional[int] = None,
        height: str = "800px",
        width: str = "100%",
        physics: bool = True,
        show_edge_labels: bool = True
    ) -> str:
        """
        Create an interactive HTML visualization of the graph.
        
        Args:
            output_path: Path to save the HTML file
            node_type_filter: Optional filter for node types
            limit: Optional limit on number of nodes
            height: Height of the visualization canvas
            width: Width of the visualization canvas
            physics: Whether to enable physics simulation
            show_edge_labels: Whether to show edge type labels
        
        Returns:
            Path to the generated HTML file
        """
        logger.info("Creating graph visualization")
        
        # Fetch nodes and edges
        nodes, edges = self.get_all_nodes_and_edges(node_type_filter, limit)
        
        if not nodes:
            logger.warning("No nodes found to visualize")
            return ""
        
        # Create pyvis network
        net = Network(
            height=height,
            width=width,
            directed=True,
            bgcolor="#222222",
            font_color="white"
        )
        
        # Configure physics
        if physics:
            net.set_options("""
            {
                "physics": {
                    "enabled": true,
                    "barnesHut": {
                        "gravitationalConstant": -2000,
                        "centralGravity": 0.1,
                        "springLength": 200,
                        "springConstant": 0.04,
                        "damping": 0.09
                    }
                }
            }
            """)
        else:
            net.set_options("""
            {
                "physics": {
                    "enabled": false
                }
            }
            """)
        
        # Add nodes with styling
        for node in nodes:
            node_id = str(node["id"])
            node_type = node.get("node_type", "default")
            label = node.get("label", "Unknown")
            properties = node.get("properties", {})
            
            # Get color for node type
            color = self.NODE_COLORS.get(node_type, self.NODE_COLORS["default"])
            
            # Create title with additional info
            title_parts = [f"Type: {node_type}", f"Label: {label}"]
            if properties:
                for key, value in list(properties.items())[:3]:  # Show first 3 properties
                    title_parts.append(f"{key}: {value}")
            title = "\\n".join(title_parts)
            
            # Determine node size based on type (papers are larger)
            size = 25 if node_type == "paper" else 15
            
            net.add_node(
                node_id,
                label=label[:30] + "..." if len(label) > 30 else label,  # Truncate long labels
                color=color,
                title=title,
                size=size,
                shape="dot" if node_type != "paper" else "box"
            )
        
        # Collect node IDs that were added
        added_node_ids = {str(node["id"]) for node in nodes}
        
        # Add edges with styling
        for edge in edges:
            from_id = str(edge["from_node_id"])
            to_id = str(edge["to_node_id"])
            edge_type = edge.get("edge_type", "default")
            confidence = edge.get("confidence", 1.0)
            properties = edge.get("properties", {})
            
            # Skip if nodes don't exist
            if from_id not in added_node_ids or to_id not in added_node_ids:
                continue
            
            # Get color for edge type
            color = self.EDGE_COLORS.get(edge_type, self.EDGE_COLORS["default"])
            
            # Create title
            title_parts = [f"Type: {edge_type}", f"Confidence: {confidence:.2f}"]
            if properties:
                for key, value in list(properties.items())[:2]:
                    title_parts.append(f"{key}: {value}")
            title = "\\n".join(title_parts)
            
            # Edge width based on confidence
            width = max(1, int(confidence * 5))
            
            # Edge label
            label = edge_type if show_edge_labels else ""
            
            net.add_edge(
                from_id,
                to_id,
                title=title,
                color=color,
                width=width,
                label=label,
                arrows="to"
            )
        
        # Save the visualization
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        net.save_graph(str(output_file))
        logger.info(f"Graph visualization saved to {output_file.absolute()}")
        
        return str(output_file.absolute())
    
    def visualize_subgraph(
        self,
        root_node_id: UUID,
        max_depth: int = 2,
        output_path: str = "graph_subgraph.html",
        height: str = "800px",
        width: str = "100%"
    ) -> str:
        """
        Visualize a subgraph starting from a root node.
        
        Args:
            root_node_id: UUID of the root node
            max_depth: Maximum depth to traverse from root
            output_path: Path to save the HTML file
            height: Height of the visualization canvas
            width: Width of the visualization canvas
        
        Returns:
            Path to the generated HTML file
        """
        logger.info(f"Creating subgraph visualization from node {root_node_id}")
        
        # BFS to collect nodes and edges
        visited_nodes = set()
        nodes_to_visit = [(root_node_id, 0)]  # (node_id, depth)
        collected_nodes = []
        collected_edges = []
        
        while nodes_to_visit:
            current_id, depth = nodes_to_visit.pop(0)
            
            if current_id in visited_nodes or depth > max_depth:
                continue
            
            visited_nodes.add(current_id)
            
            # Get node
            node = self.repository.get_node_supabase(current_id)
            if not node:
                continue
            
            collected_nodes.append(node)
            
            if depth < max_depth:
                # Get outgoing edges
                outgoing = self.repository.get_edges_from_node(current_id)
                for edge in outgoing:
                    to_id = UUID(str(edge["to_node_id"]))
                    collected_edges.append(edge)
                    if to_id not in visited_nodes:
                        nodes_to_visit.append((to_id, depth + 1))
                
                # Get incoming edges
                incoming = self.repository.get_edges_to_node(current_id)
                for edge in incoming:
                    from_id = UUID(str(edge["from_node_id"]))
                    collected_edges.append(edge)
                    if from_id not in visited_nodes:
                        nodes_to_visit.append((from_id, depth + 1))
        
        # Create visualization with collected nodes and edges
        # Temporarily store nodes and edges
        self._temp_nodes = collected_nodes
        self._temp_edges = collected_edges
        
        # Use the main visualize method but with our collected data
        return self._visualize_custom(
            collected_nodes,
            collected_edges,
            output_path,
            height,
            width
        )
    
    def _visualize_custom(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        output_path: str,
        height: str,
        width: str
    ) -> str:
        """Internal method to visualize custom node/edge sets."""
        if not nodes:
            logger.warning("No nodes provided for visualization")
            return ""
        
        # Create pyvis network
        net = Network(
            height=height,
            width=width,
            directed=True,
            bgcolor="#222222",
            font_color="white"
        )
        
        # Configure physics
        net.set_options("""
        {
            "physics": {
                "enabled": true,
                "barnesHut": {
                    "gravitationalConstant": -2000,
                    "centralGravity": 0.1,
                    "springLength": 200,
                    "springConstant": 0.04,
                    "damping": 0.09
                }
            }
        }
        """)
        
        # Add nodes
        node_ids = set()
        for node in nodes:
            node_id = str(node["id"])
            node_ids.add(node_id)
            node_type = node.get("node_type", "default")
            label = node.get("label", "Unknown")
            properties = node.get("properties", {})
            
            color = self.NODE_COLORS.get(node_type, self.NODE_COLORS["default"])
            
            title_parts = [f"Type: {node_type}", f"Label: {label}"]
            if properties:
                for key, value in list(properties.items())[:3]:
                    title_parts.append(f"{key}: {value}")
            title = "\\n".join(title_parts)
            
            size = 25 if node_type == "paper" else 15
            
            net.add_node(
                node_id,
                label=label[:30] + "..." if len(label) > 30 else label,
                color=color,
                title=title,
                size=size,
                shape="dot" if node_type != "paper" else "box"
            )
        
        # Add edges
        for edge in edges:
            from_id = str(edge["from_node_id"])
            to_id = str(edge["to_node_id"])
            
            if from_id not in node_ids or to_id not in node_ids:
                continue
            
            edge_type = edge.get("edge_type", "default")
            confidence = edge.get("confidence", 1.0)
            properties = edge.get("properties", {})
            
            color = self.EDGE_COLORS.get(edge_type, self.EDGE_COLORS["default"])
            
            title_parts = [f"Type: {edge_type}", f"Confidence: {confidence:.2f}"]
            if properties:
                for key, value in list(properties.items())[:2]:
                    title_parts.append(f"{key}: {value}")
            title = "\\n".join(title_parts)
            
            width_edge = max(1, int(confidence * 5))
            
            net.add_edge(
                from_id,
                to_id,
                title=title,
                color=color,
                width=width_edge,
                label=edge_type,
                arrows="to"
            )
        
        # Save
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        net.save_graph(str(output_file))
        logger.info(f"Graph visualization saved to {output_file.absolute()}")
        
        return str(output_file.absolute())

