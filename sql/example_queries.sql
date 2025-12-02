-- Example Queries for the Paper Knowledge Graph

-- 1. Find all papers that improve on the original 3DGS paper
-- (Assuming the original paper has a known node_id or label)
SELECT 
    p.title,
    p.year,
    p.venue,
    e.confidence,
    e.properties->>'rationale' as improvement_rationale
FROM papers p
JOIN nodes n ON p.node_id = n.id
JOIN edges e ON e.from_node_id = n.id
JOIN nodes target ON e.to_node_id = target.id
WHERE e.edge_type = 'IMPROVES_ON'
  AND target.label ILIKE '%3D Gaussian Splatting%'
  AND target.node_type = 'paper'
ORDER BY e.confidence DESC, p.year DESC;

-- 2. List all concepts introduced by a specific paper
-- (Replace 'PAPER_NODE_ID' with actual UUID)
SELECT 
    c.label as concept_name,
    c.properties->>'description' as concept_description,
    e.properties->>'evidence_span' as evidence_location
FROM nodes p
JOIN edges e ON e.from_node_id = p.id
JOIN nodes c ON e.to_node_id = c.id
WHERE p.id = 'PAPER_NODE_ID'::uuid
  AND e.edge_type = 'INTRODUCES'
  AND c.node_type = 'concept'
ORDER BY c.label;

-- 3. Show papers that extend Paper Y via concept Z
-- (Replace placeholders with actual values)
SELECT DISTINCT
    p.title,
    p.year,
    e1.properties->>'rationale' as extension_rationale,
    e2.confidence as concept_confidence
FROM papers p
JOIN nodes paper_node ON p.node_id = paper_node.id
JOIN edges e1 ON e1.from_node_id = paper_node.id
JOIN nodes concept_node ON e1.to_node_id = concept_node.id
JOIN edges e2 ON e2.from_node_id = concept_node.id
JOIN nodes target_paper ON e2.to_node_id = target_paper.id
WHERE e1.edge_type = 'INTRODUCES'
  AND e2.edge_type = 'USES_CONCEPT'
  AND concept_node.label = 'CONCEPT_Z'
  AND target_paper.id = 'PAPER_Y_NODE_ID'::uuid
ORDER BY e1.confidence DESC;

-- 4. Find all methods used across papers
SELECT 
    m.label as method_name,
    COUNT(DISTINCT e.from_node_id) as paper_count,
    ARRAY_AGG(DISTINCT p.title) as papers_using_method
FROM nodes m
JOIN edges e ON e.to_node_id = m.id
JOIN nodes paper_node ON e.from_node_id = paper_node.id
JOIN papers p ON p.node_id = paper_node.id
WHERE m.node_type = 'method'
  AND e.edge_type IN ('INTRODUCES', 'USES_CONCEPT')
GROUP BY m.id, m.label
ORDER BY paper_count DESC;

-- 5. Get papers and their evaluation metrics
SELECT 
    p.title,
    p.year,
    m.label as metric_name,
    e.properties->>'evidence_span' as evaluation_section
FROM papers p
JOIN nodes paper_node ON p.node_id = paper_node.id
JOIN edges e ON e.from_node_id = paper_node.id
JOIN nodes m ON e.to_node_id = m.id
WHERE m.node_type = 'metric'
  AND e.edge_type = 'EVALUATES_WITH'
ORDER BY p.year DESC, p.title;

-- 6. Find related papers (connected via concepts)
SELECT DISTINCT
    p1.title as paper1,
    p2.title as paper2,
    concept.label as shared_concept,
    e1.edge_type as paper1_relation,
    e2.edge_type as paper2_relation
FROM papers p1
JOIN nodes n1 ON p1.node_id = n1.id
JOIN edges e1 ON e1.from_node_id = n1.id
JOIN nodes concept ON e1.to_node_id = concept.id
JOIN edges e2 ON e2.to_node_id = concept.id
JOIN nodes n2 ON e2.from_node_id = n2.id
JOIN papers p2 ON p2.node_id = n2.id
WHERE p1.node_id != p2.node_id
  AND concept.node_type = 'concept'
ORDER BY p1.title, p2.title;

-- 7. Get citation network (if CITES edges exist)
SELECT 
    p1.title as citing_paper,
    p1.year as citing_year,
    p2.title as cited_paper,
    p2.year as cited_year,
    e.confidence
FROM papers p1
JOIN nodes n1 ON p1.node_id = n1.id
JOIN edges e ON e.from_node_id = n1.id
JOIN nodes n2 ON e.to_node_id = n2.id
JOIN papers p2 ON p2.node_id = n2.id
WHERE e.edge_type = 'CITES'
ORDER BY p1.year DESC;

-- 8. Find most influential concepts (by number of papers using them)
SELECT 
    c.label as concept,
    COUNT(DISTINCT e.from_node_id) as usage_count,
    ARRAY_AGG(DISTINCT p.title ORDER BY p.title) FILTER (WHERE p.title IS NOT NULL) as papers
FROM nodes c
LEFT JOIN edges e ON e.to_node_id = c.id AND e.edge_type IN ('INTRODUCES', 'USES_CONCEPT')
LEFT JOIN nodes paper_node ON e.from_node_id = paper_node.id
LEFT JOIN papers p ON p.node_id = paper_node.id
WHERE c.node_type = 'concept'
GROUP BY c.id, c.label
ORDER BY usage_count DESC
LIMIT 20;

-- 9. Get paper improvement chain (papers that improve on papers that improve on...)
WITH RECURSIVE improvement_chain AS (
    -- Base case: start from a specific paper
    SELECT 
        n.id as paper_id,
        p.title,
        0 as depth,
        ARRAY[n.id] as path
    FROM nodes n
    JOIN papers p ON p.node_id = n.id
    WHERE n.id = 'START_PAPER_ID'::uuid  -- Replace with actual ID
    
    UNION ALL
    
    -- Recursive case: find papers that improve on current paper
    SELECT 
        n2.id,
        p2.title,
        ic.depth + 1,
        ic.path || n2.id
    FROM improvement_chain ic
    JOIN edges e ON e.to_node_id = ic.paper_id AND e.edge_type = 'IMPROVES_ON'
    JOIN nodes n2 ON e.from_node_id = n2.id
    JOIN papers p2 ON p2.node_id = n2.id
    WHERE NOT n2.id = ANY(ic.path)  -- Prevent cycles
      AND ic.depth < 5  -- Limit depth
)
SELECT 
    title,
    depth,
    path
FROM improvement_chain
ORDER BY depth, title;

-- 10. Find papers by dataset usage
SELECT 
    p.title,
    p.year,
    d.label as dataset_name,
    e.properties->>'evidence_span' as usage_location
FROM papers p
JOIN nodes paper_node ON p.node_id = paper_node.id
JOIN edges e ON e.from_node_id = paper_node.id
JOIN nodes d ON e.to_node_id = d.id
WHERE d.node_type = 'dataset'
  AND e.edge_type IN ('USES_DATASET', 'EVALUATES_ON')
ORDER BY p.year DESC, d.label;

