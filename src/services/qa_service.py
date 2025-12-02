from services.graph_service import GraphService
from utils.llm import LLMClient


class QAService:
    def __init__(self, graph_service: GraphService, llm_client: LLMClient):
        self.graph_service = graph_service
        self.llm = llm_client

    def answer_question(self, question: str) -> str:
        seeds = self.graph_service.semantic_search_papers(question, k=1)
        context_lines = []

        for p in seeds:
            title = p.get("title") or p.get("label")
            year = p.get("year")
            abstract = p.get("node_properties", {}).get("abstract", "")
            context_lines.append(f"- {title} ({year}): {abstract}...")

        context = "\n".join(context_lines)

        system_prompt = "You are a research assistant answering questions using only the supplied papers."
        user_prompt = f"Question:\n{question}\n\nRelevant papers:\n{context}\n\nAnswer the question."

        return self.llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=800,
        )
