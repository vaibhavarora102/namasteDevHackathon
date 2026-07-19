"""
Shared knowledge base.

Holds only distilled, generalized, anonymized knowledge snippets that are
useful across sessions and agents (facts, strategies, corrections, style
lessons expressed as general rules). It must never contain names,
identifiers, or one-off personal specifics from a private session -- the
extractor (extractor.py) is responsible for enforcing that boundary before
anything is written here.
"""
import time
import uuid
from typing import Dict, List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document

from config import SHARED_KB_DIR, get_embeddings


class SharedKnowledgeStore:
    def __init__(self, persist_dir: str = SHARED_KB_DIR):
        self.persist_dir = persist_dir
        self._embeddings = get_embeddings()
        self._store = Chroma(
            collection_name="shared_knowledge",
            embedding_function=self._embeddings,
            persist_directory=self.persist_dir,
        )

    def add_knowledge(self, snippets: List[str], source_agent_id: str, topic: Optional[str] = None):
        docs = [
            Document(
                page_content=snippet.strip(),
                metadata={
                    "source_agent_id": source_agent_id,
                    "topic": topic or "general",
                    "created_at": time.time(),
                    "knowledge_id": str(uuid.uuid4()),
                },
            )
            for snippet in snippets
            if snippet and snippet.strip()
        ]
        if docs:
            self._store.add_documents(docs)

    def query(self, query_text: str, k: int = 4) -> List[Dict]:
        results = self._store.similarity_search_with_score(query_text, k=k)
        return [
            {"content": doc.page_content, "metadata": doc.metadata, "score": score}
            for doc, score in results
        ]

    def all_knowledge(self, limit: int = 200) -> List[Dict]:
        data = self._store.get(limit=limit)
        out = [
            {"content": content, "metadata": metadata}
            for content, metadata in zip(data.get("documents", []), data.get("metadatas", []))
        ]
        out.sort(key=lambda x: x["metadata"].get("created_at", 0), reverse=True)
        return out

    def count(self) -> int:
        return self._store._collection.count()
