from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class RefusalReason(str, Enum):
    NO_RELEVANT_EVIDENCE = "no_relevant_evidence"
    MISSING_CITATION = "missing_citation"
    CITATION_MISMATCH = "citation_mismatch"
    GENERATION_ERROR = "generation_error"
    AMBIGUOUS_QUESTION = "ambiguous_question"
    OUT_OF_SCOPE = "out_of_scope"


class DocumentStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


# ---------- Ingestion ----------

class IngestResult(BaseModel):
    document_id: str
    file_name: str
    status: str  # "ingested" | "skipped_duplicate" | "failed"
    chunks_created: int = 0
    error: Optional[str] = None

class IngestSummary(BaseModel):
    total_documents: int
    ingested: int
    skipped_duplicate: int
    failed: int
    total_chunks_created: int
    results: list[IngestResult]
    
class DocumentSummary(BaseModel):
    document_id: str
    title: str
    version: str
    effective_date: str
    status: DocumentStatus
    chunk_count: int


# ---------- Retrieval ----------

class RetrievedChunk(BaseModel):
    document_id: str
    document_title: str
    section: str
    text: str
    score: float


# ---------- Answering ----------

class Citation(BaseModel):
    document_id: str
    document_title: str
    section: str


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=3)
    top_k: Optional[int] = None


class AnswerResponse(BaseModel):
    question_id: str = Field(default_factory=lambda: str(uuid4()))
    answer: str
    supported: bool
    citations: list[Citation] = Field(default_factory=list)
    retrieved_sources: list[RetrievedChunk] = Field(default_factory=list)
    confidence: float
    reason_for_refusal: Optional[RefusalReason] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DebugTrace(BaseModel):
    question_id: str
    query: str
    retrieved_chunks: list[RetrievedChunk]
    final_context_sent_to_model: str
    raw_model_output: str
    final_answer: AnswerResponse
