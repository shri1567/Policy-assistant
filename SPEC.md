# SPEC.md — Policy Q&A Assistant with Evidence

## 1. Problem
Employees ask policy questions across leave, travel, remote work, security, onboarding, and acceptable use. Answers must be grounded strictly in the supplied policy documents — no answering from general/world knowledge, and no answering about personal employee records.

## 2. Non-Goals
- No authentication/user management (out of scope for this project)
- No policy authoring/editing UI — ingestion is file-based
- No multi-tenant support — single policy collection

## 3. Core Design Decisions
- **Vector store**: a local JSON file (`data/store.json`) instead of Postgres/pgvector. This was a deliberate simplification — Docker required virtualization that wasn't available on the dev machine, and cloud Postgres (Supabase) added setup friction (IPv6-only direct connections, pooler configuration) that outweighed the benefit for a project this size. Cosine similarity is computed by hand in `app/db.py`, doing in plain Python what pgvector's `<=>` operator does inside the database. Documented here as a conscious tradeoff: it trades away the pgvector practice from the internship curriculum in exchange for zero infrastructure setup and faster iteration.
- **Embeddings + generation**: Gemini API — `gemini-embedding-001` for embeddings, `gemini-3.6-flash` for generation. Both model names were updated during development after the originally-planned `text-embedding-004` and `gemini-2.0-flash` were deprecated by Google mid-project. This is worth noting as a real lesson: hosted model APIs retire versions on a schedule outside your control, so model names belong in config (`.env`), never hardcoded, and should be expected to need updates over a project's lifetime.
- **Chunking**: section-aware — split on `## Section N` markdown headers, so every chunk is naturally labeled with its section. No further sub-chunking of long sections was implemented; in practice none of the 6 policy documents have a single section long enough to need it, so this was simplified out rather than built speculatively.
- **Orchestration**: LangGraph 3-node graph — `retrieve → generate_answer → validate_citations`. The validation node is a deterministic check (not another LLM call) that confirms every cited (document_id, section) pair in the model's output actually appears in the retrieved chunk set. If not, the answer is forced to `supported: false`.
- **Refusal logic**: refusal is not just "no chunks found" — it's a threshold check. If the top retrieval score is below `SIMILARITY_THRESHOLD` (configurable, default 0.55), or the LLM itself states insufficient evidence, the response is marked unsupported.
- **Retrieval width**: `DEFAULT_TOP_K` is configurable (default 4, raised to 6 during testing). Multi-document questions — ones needing evidence from two policies at once — were initially missing relevant chunks at top_k=4; widening the retrieval window fixed this without any change to the underlying retrieval logic. This is the main lever to tune if a question's correct evidence isn't surfacing.
- **Idempotent ingestion**: each document is hashed (SHA-256 of raw content); the hash is stored alongside chunks, and re-ingesting a document with the same hash is a no-op, reported explicitly in the ingest summary response.
- **No retry logic on LLM calls**: `app/llm.py` calls Gemini directly with no retry/backoff wrapper. This was a deliberate simplification (retries added complexity without proportionate learning value at this scope) — a failed call surfaces immediately as a clear error rather than being silently retried.

## 4. Data Flow
```
POST /documents/ingest
  → for each doc in manifest.json: load file → hash check (skip if duplicate)
  → section-aware chunk → Gemini embed each section
  → store in data/store.json as {document_id, section, chunk_text, embedding}
  → return IngestSummary: total_documents, ingested, skipped_duplicate, failed,
    total_chunks_created, plus per-document results

POST /questions
  → embed question (Gemini) → cosine similarity search against every stored chunk
    (plain Python, app/db.py), return top_k highest-scoring chunks
  → LangGraph: retrieve (already done) → generate_answer (Gemini, evidence-only prompt,
    short-circuits to refusal if top score < SIMILARITY_THRESHOLD)
    → validate_citations (deterministic cross-check against retrieved chunk set)
  → store question record (question, retrieved_chunks, answer, debug trace) in store.json
  → return AnswerResponse

GET /questions/{id}/debug
  → return full trace: query, retrieved chunks + scores, final context sent to the
    model, raw model output, cited sources

GET /  →  serves app/static/index.html, a small vanilla JS frontend that calls the
  above endpoints directly — same-origin fetch, no separate backend needed.
```

## 5. Response Schemas (matches Project 2 doc, Section 10D)
```python
class AnswerResponse(BaseModel):
    question_id: str
    answer: str
    supported: bool
    citations: list[Citation]          # empty if supported=False
    retrieved_sources: list[RetrievedChunk]
    confidence: float                  # 0-1, top retrieval score
    reason_for_refusal: RefusalReason | None  # populated only if supported=False
    created_at: datetime

class IngestSummary(BaseModel):
    total_documents: int
    ingested: int
    skipped_duplicate: int
    failed: int
    total_chunks_created: int
    results: list[IngestResult]        # per-document detail
```

## 6. Failure Handling Map (Section 4.6 of requirements)
| Failure | Handling |
|---|---|
| Unsupported document type | Reject at ingestion with `UnsupportedDocumentType`, surfaced as 415 with allowed extensions |
| Empty document | Reject at ingestion with `EmptyDocumentError`, surfaced as 422 |
| Duplicate ingestion | Content hash match → skip, `status: "skipped_duplicate"` in the per-document result, rolled up in `IngestSummary.skipped_duplicate` |
| Embedding/generation API failure | No retry wrapper (see Section 3) — the exception propagates and is caught by the top-level exception handler in `main.py`, returned as a 500 with the underlying error message |
| Vector-store failure | The local JSON store has no separate failure mode beyond normal file I/O errors, which surface the same way as above |
| No relevant chunks | `supported: false`, `reason_for_refusal: "no_relevant_evidence"` — short-circuited before an LLM call is made at all if the top score is below threshold |
| Malformed model response (not valid JSON) | `parse_model_json()` in `app/llm.py` returns `None` instead of raising; the graph node checks for `None` and refuses cleanly with `reason_for_refusal: "generation_error"` |
| Missing citation | If `supported: true` but citations list is empty → `validate_citations` forces `supported: false`, `reason_for_refusal: "missing_citation"` |
| Citation not in retrieved evidence | `validate_citations` cross-checks every `(document_id, section)` pair against the retrieved set; any mismatch forces `supported: false`, `reason_for_refusal: "citation_mismatch"` |

## 7. Out-of-scope edge cases (documented, not handled)
- Concurrent ingestion of the same document (race condition on hash check, and on concurrent writes to `store.json`) — acceptable for a single-day internal tool with one user, not solved with file locking here.
- The local store re-scans every chunk on every question (O(n) similarity search) — fine at this document collection's size; would need a real vector index (i.e., the originally-planned pgvector) to scale to a large policy library.