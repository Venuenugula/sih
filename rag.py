"""ChromaDB retrieval with Sentence Transformers. No LLM in this phase."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from config import CHROMA_PATH, EMBEDDING_MODEL, RAG_TOP_K, ensure_folders

COLLECTION_NAME = "documents"


@lru_cache(maxsize=1)
def _embedder() -> SentenceTransformer:
    try:
        return SentenceTransformer(EMBEDDING_MODEL)
    except Exception:
        return SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)


def _collection():
    ensure_folders()
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(name=COLLECTION_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = _embedder().encode(texts, show_progress_bar=False)
    return vectors.tolist()


def indexed_count() -> int:
    return int(_collection().count())


def index_chunks(chunks: list[dict]) -> int:
    """Store chunk dicts with text, filename, and page."""
    if not chunks:
        return 0
    collection = _collection()
    filenames = {str(chunk["filename"]) for chunk in chunks}
    for name in filenames:
        try:
            collection.delete(where={"filename": name})
        except Exception:
            pass

    ids = []
    documents = []
    metadatas = []
    for i, chunk in enumerate(chunks):
        ids.append(f"{chunk['filename']}::p{chunk['page']}::{i}")
        documents.append(chunk["text"])
        metadatas.append(
            {
                "filename": str(chunk["filename"]),
                "page": int(chunk["page"]),
            }
        )

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embed_texts(documents),
    )
    return len(ids)


def index_pdf(pdf_path: str | Path) -> int:
    from documents import process_pdf

    result = process_pdf(pdf_path)
    return index_chunks(result["chunk_records"])


def search_documents(question: str, top_k: int | None = None) -> list[dict]:
    """Return the closest chunks as text, filename, and page."""
    query = (question or "").strip()
    if not query:
        return []
    collection = _collection()
    total = collection.count()
    if total == 0:
        return []
    k = min(top_k or RAG_TOP_K, total)
    result = collection.query(
        query_embeddings=embed_texts([query]),
        n_results=k,
        include=["documents", "metadatas"],
    )
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    hits = []
    for text, meta in zip(documents, metadatas):
        meta = meta or {}
        hits.append(
            {
                "text": text or "",
                "filename": str(meta.get("filename") or ""),
                "page": int(meta.get("page") or 0),
            }
        )
    return hits
