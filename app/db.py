import json
import math
from pathlib import Path
from typing import Optional

STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "store.json"
_EMPTY_STORE = {"documents": {}, "chunks": [], "questions": {}}


def _load() -> dict:
    if not STORE_PATH.exists():
        return json.loads(json.dumps(_EMPTY_STORE))
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def _save(store: dict):
    STORE_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")


def init_db():
    if not STORE_PATH.exists():
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _save(_EMPTY_STORE)


def get_document_hash(document_id: str) -> Optional[str]:
    store = _load()
    doc = store["documents"].get(document_id)
    return doc["content_hash"] if doc else None


def upsert_document(document_id, file_name, title, version, effective_date, content_hash):
    store = _load()
    store["documents"][document_id] = {
        "file_name": file_name,
        "title": title,
        "version": version,
        "effective_date": effective_date,
        "status": "active",
        "content_hash": content_hash,
    }
    _save(store)


def delete_chunks_for_document(document_id: str):
    store = _load()
    store["chunks"] = [c for c in store["chunks"] if c["document_id"] != document_id]
    _save(store)


def insert_chunk(document_id: str, section: str, chunk_text: str, embedding: list):
    store = _load()
    store["chunks"].append({
        "document_id": document_id,
        "section": section,
        "chunk_text": chunk_text,
        "embedding": embedding,
    })
    _save(store)


def _cosine_similarity(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def similarity_search(query_embedding, top_k: int):
    store = _load()
    scored = []
    for chunk in store["chunks"]:
        score = _cosine_similarity(query_embedding, chunk["embedding"])
        doc = store["documents"].get(chunk["document_id"], {})
        scored.append((
            chunk["document_id"],
            doc.get("title", chunk["document_id"]),
            chunk["section"],
            chunk["chunk_text"],
            score,
        ))
    scored.sort(key=lambda row: row[4], reverse=True)
    return scored[:top_k]


def list_documents():
    store = _load()
    rows = []
    for doc_id, doc in store["documents"].items():
        chunk_count = sum(1 for c in store["chunks"] if c["document_id"] == doc_id)
        rows.append((doc_id, doc["title"], doc["version"], doc["effective_date"], doc["status"], chunk_count))
    return sorted(rows, key=lambda r: r[0])


def save_question_record(question_id, question_text, answer_json, debug_json):
    store = _load()
    store["questions"][question_id] = {
        "question_text": question_text,
        "answer_json": answer_json,
        "debug_json": debug_json,
    }
    _save(store)


def get_question_record(question_id: str):
    store = _load()
    record = store["questions"].get(question_id)
    if not record:
        return None
    return (record["question_text"], record["answer_json"], record["debug_json"])