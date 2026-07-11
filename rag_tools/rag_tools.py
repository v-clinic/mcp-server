"""
vClinic RAG tool — searches the clinic's internal knowledge base using
semantic vector search.

Knowledge base covers:
  - Drug formulary (approved medications, dosing, tiers, contraindications)
  - Clinical protocols (CAP, AGE, HTN, T2DM, fever)
  - Clinic SOPs (registration, vitals, lab/radiology ordering, discharge)

The Pinecone index is built once from the knowledge_base/ markdown files.
Subsequent calls reuse the persisted index.

vClinic agents call search_clinic_knowledge() per the action the agent is conducting.

TODO: Add a tool to refresh the index when knowledge base docs are updated.
"""

from __future__ import annotations

import json
import os
import pathlib
import re

from cache.decorators import cached
from cache.keys import is_json_success, rag_search_key

# ---------------------------------------------------------------------------
# Paths & index config
# ---------------------------------------------------------------------------
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent
_KB_DIR = _PROJECT_ROOT / "knowledge_base"
_INDEX_NAME = "vclinic-knowledge"
_EMBED_MODEL = "text-embedding-3-small"
_EMBED_DIM = 1536
_PINECONE_HOST = "http://localhost:5080"  # For local Pinecone dev server
_PINECONE_APIKEY = "local-dev-key"  # For local Pinecone dev server (not a real key, just needs to be set)
# ---------------------------------------------------------------------------
# Globals initialised once at server start-up
# ---------------------------------------------------------------------------
_pinecone_index = None

def _get_openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it before starting the MCP server."
        )
    return key

def _get_pinecone_client():
    from pinecone.grpc import PineconeGRPC
    return PineconeGRPC(api_key=_PINECONE_APIKEY, host=_PINECONE_HOST)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using OpenAI text-embedding-3-small."""
    from openai import OpenAI
    client = OpenAI(api_key=_get_openai_api_key())
    response = client.embeddings.create(model=_EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]

def _chunk_markdown(text: str, source: str, chunk_size: int = 600, overlap: int = 100) -> list[dict]:
    """
    Hardcoded chunk and overlap size for demonstration purposes 
    Split markdown text into overlapping chunks.
    Tries to split on section headings first, then falls back to sliding window.
    Returns list of {"text": ..., "source": ..., "section": ...}.
    """
    # Split on ## headings to keep sections together
    sections = re.split(r"\n(?=#{1,3} )", text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # Extract heading for metadata
        heading_match = re.match(r"^(#{1,3} .+)", section)
        heading = heading_match.group(1).lstrip("#").strip() if heading_match else source

        # If section fits in one chunk, keep as-is
        if len(section) <= chunk_size:
            chunks.append({"text": section, "source": source, "section": heading})
        else:
            # Sliding window fallback
            words = section.split()
            i = 0
            while i < len(words):
                window = words[i : i + chunk_size // 5]  # ~5 chars/word estimate
                chunk_text = " ".join(window)
                chunks.append({"text": chunk_text, "source": source, "section": heading})
                i += (chunk_size - overlap) // 5
    return chunks


def _build_index() -> object:
    """Load knowledge base docs, chunk, embed with OpenAI, and upsert into Pinecone."""
    from pinecone import ServerlessSpec

    pc = _get_pinecone_client()

    # Delete old index if it exists (clean rebuild)
    existing = [idx.name for idx in pc.list_indexes()]
    if _INDEX_NAME in existing:
        pc.delete_index(_INDEX_NAME)

    pc.create_index(
        name=_INDEX_NAME,
        dimension=_EMBED_DIM,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
    index = pc.Index(_INDEX_NAME)

    all_chunks: list[dict] = []
    md_files = sorted(_KB_DIR.glob("*.md"))
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        chunks = _chunk_markdown(text, source=md_file.name)
        all_chunks.extend(chunks)

    if not all_chunks:
        raise RuntimeError(f"No markdown files found in {_KB_DIR}")

    # Embed and upsert in batches
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        embeddings = _embed_texts([c["text"] for c in batch])
        vectors = [
            {
                "id": f"chunk_{i + j}",
                "values": embeddings[j],
                "metadata": {
                    "source": batch[j]["source"],
                    "section": batch[j]["section"],
                    "text": batch[j]["text"],
                },
            }
            for j in range(len(batch))
        ]
        index.upsert(vectors=vectors)

    print(f"[RAG] Indexed {len(all_chunks)} chunks from {len(md_files)} files → Pinecone index '{_INDEX_NAME}'", flush=True)
    return index


def _get_index():
    """Return the Pinecone index, building it from scratch if needed."""
    global _pinecone_index
    if _pinecone_index is not None:
        return _pinecone_index

    pc = _get_pinecone_client()
    existing = [idx.name for idx in pc.list_indexes()]
    if _INDEX_NAME in existing:
        index = pc.Index(_INDEX_NAME)
        stats = index.describe_index_stats()
        if stats.total_vector_count > 0:
            _pinecone_index = index
            return _pinecone_index

    # Build from scratch
    _pinecone_index = _build_index()
    return _pinecone_index


@cached(
    namespace="rag_search",
    key_fn=lambda query, max_results=5, **_: rag_search_key(query, max_results),
    should_cache=is_json_success,
)
def search_clinic_knowledge(query: str, max_results: int = 5) -> str:
    """Search vClinic's internal knowledge base for protocols, drug formulary, and SOPs.

    Use this BEFORE making clinical decisions to check:
    - Drug dosing, formulary tier, contraindications, and local resistance data
    - Treatment protocols (CAP, gastroenteritis, HTN, diabetes, fever)
    - Ordering requirements (what labs/imaging to order and when)
    - Clinic SOPs (documentation requirements, vital sign thresholds, discharge criteria)

    This searches the clinic's own vetted guidelines — prefer this over external
    literature when making treatment decisions for vClinic patients.

    Args:
        query:       Clinical question (e.g. "amoxicillin dosing pneumonia",
                     "hypertension first-line treatment", "CBC critical values").
        max_results: Number of relevant chunks to return (1–10, default 5).

    Returns:
        JSON string with a list of matching knowledge base excerpts, each with
        source file, section heading, relevance score, and text content.
    """
    max_results = max(1, min(max_results, 10))
    try:
        index = _get_index()
        query_embedding = _embed_texts([query])[0]
        results = index.query(
            vector=query_embedding,
            top_k=max_results,
            include_metadata=True,
        )

        output = []
        for match in results.matches:
            output.append({
                "source": match.metadata.get("source", ""),
                "section": match.metadata.get("section", ""),
                "relevance": round(match.score, 3),
                "content": match.metadata.get("text", ""),
            })

        if not output:
            return json.dumps({"results": [], "message": "No relevant knowledge found."})

        return json.dumps({"results": output}, indent=2)

    except Exception as exc:
        return json.dumps({"error": str(exc)})


def init_rag_collection() -> None:
    """Eagerly build or load the Pinecone index at server start-up.

    Call this once after the MCP server is initialised so the first
    search_clinic_knowledge() call is not slowed down by index construction.
    """
    _get_index()
