from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.graph import run_question
from app.ingest import (
    EmptyDocumentError,
    UnsupportedDocumentType,
    ingest_document,
    ingest_from_manifest,
)
from app.schemas import (
    AnswerResponse,
    DebugTrace,
    DocumentSummary,
    IngestResult,
    IngestSummary,
    QuestionRequest,
)

app = FastAPI(title="Policy Q&A Assistant", version="0.1.0")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POLICIES_DIR = DATA_DIR / "policies"
MANIFEST_PATH = DATA_DIR / "manifest.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/")
def serve_ui():
    """The simple chat-style frontend. Swagger docs are still at /docs."""
    return FileResponse(STATIC_DIR / "index.html")


@app.on_event("startup")
def startup():
    db.init_db()


@app.post("/documents/ingest", response_model=IngestSummary)
def ingest_documents():
    """Ingests every document listed in data/manifest.json. Idempotent —
    re-running this after no changes returns 'skipped_duplicate' for all docs."""
    if not MANIFEST_PATH.exists():
        raise HTTPException(status_code=404, detail="manifest.json not found")
    results = ingest_from_manifest(MANIFEST_PATH, POLICIES_DIR)

    return IngestSummary(
        total_documents=len(results),
        ingested=sum(1 for r in results if r.status == "ingested"),
        skipped_duplicate=sum(1 for r in results if r.status == "skipped_duplicate"),
        failed=sum(1 for r in results if r.status == "failed"),
        total_chunks_created=sum(r.chunks_created for r in results),
        results=results,
    )


@app.post("/documents/ingest/upload", response_model=IngestResult)
async def ingest_uploaded_document(file: UploadFile, document_id: str | None = None):
    """Ad-hoc single-file ingestion, separate from the manifest-driven bulk path."""
    doc_id = document_id or f"UPLOAD-{uuid4().hex[:8]}"
    tmp_path = Path("/tmp") / file.filename
    content = await file.read()
    tmp_path.write_bytes(content)

    try:
        return ingest_document(tmp_path, doc_id)
    except UnsupportedDocumentType as e:
        raise HTTPException(status_code=415, detail=str(e))
    except EmptyDocumentError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/documents", response_model=list[DocumentSummary])
def get_documents():
    rows = db.list_documents()
    return [
        DocumentSummary(
            document_id=r[0], title=r[1], version=r[2], effective_date=r[3],
            status=r[4], chunk_count=r[5],
        )
        for r in rows
    ]


@app.post("/questions", response_model=AnswerResponse)
def ask_question(payload: QuestionRequest):
    state = run_question(payload.question, payload.top_k)
    answer = state["answer"]
    db.save_question_record(
        answer.question_id,
        payload.question,
        answer.model_dump(mode="json"),
        {
            "query": payload.question,
            "retrieved_chunks": [c.model_dump(mode="json") for c in state.get("retrieved_chunks", [])],
            "final_context_sent_to_model": state.get("final_context", ""),
            "raw_model_output": state.get("raw_model_output", ""),
        },
    )
    return answer


@app.get("/questions/{question_id}", response_model=AnswerResponse)
def get_question(question_id: str):
    row = db.get_question_record(question_id)
    if not row:
        raise HTTPException(status_code=404, detail="question_id not found")
    _, answer_json, _ = row
    return AnswerResponse.model_validate(answer_json)


@app.get("/questions/{question_id}/debug", response_model=DebugTrace)
def get_question_debug(question_id: str):
    row = db.get_question_record(question_id)
    if not row:
        raise HTTPException(status_code=404, detail="question_id not found")
    question_text, answer_json, debug_json = row
    return DebugTrace(
        question_id=question_id,
        query=debug_json["query"],
        retrieved_chunks=debug_json["retrieved_chunks"],
        final_context_sent_to_model=debug_json["final_context_sent_to_model"],
        raw_model_output=debug_json["raw_model_output"],
        final_answer=AnswerResponse.model_validate(answer_json),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {exc}"})
