"""
Ingestion pipeline: load a policy file -> split into sections -> embed each
section -> store in pgvector. Skips re-ingesting a document that hasn't changed.
"""
import hashlib
import json
import re
from pathlib import Path

from app import db
from app.llm import embed_text
from app.schemas import IngestResult

ALLOWED_EXTENSIONS = {".md", ".txt"}
SECTION_HEADER_RE = re.compile(r"^##\s+(Section\s+\d+.*)$", re.MULTILINE)


class UnsupportedDocumentType(Exception):
    pass


class EmptyDocumentError(Exception):
    pass


def hash_content(text: str) -> str:
    """Same text always produces the same hash. Used to detect duplicates."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_title(text: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else "Untitled Document"


def extract_field(text: str, label: str) -> str:
    match = re.search(rf"\*\*{label}:\*\*\s*(.+)", text)
    return match.group(1).strip() if match else "unknown"


def split_into_sections(text: str) -> list[tuple[str, str]]:
    """Splits a policy document into (section_label, section_text) pairs,
    using '## Section N — Title' markdown headers as the split points.
    If there are no headers, the whole document becomes one section."""
    headers = list(SECTION_HEADER_RE.finditer(text))
    if not headers:
        return [("Full Document", text.strip())]

    sections = []
    for i, header in enumerate(headers):
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        label = header.group(1).strip()
        body = text[start:end].strip()
        if body:
            sections.append((label, body))
    return sections


def ingest_document(file_path: Path, document_id: str) -> IngestResult:
    if file_path.suffix not in ALLOWED_EXTENSIONS:
        raise UnsupportedDocumentType(f"'{file_path.suffix}' not supported. Allowed: {ALLOWED_EXTENSIONS}")

    raw_text = file_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        raise EmptyDocumentError(f"{file_path.name} is empty")

    content_hash = hash_content(raw_text)
    if db.get_document_hash(document_id) == content_hash:
        return IngestResult(document_id=document_id, file_name=file_path.name, status="skipped_duplicate")

    title = extract_title(raw_text)
    version = extract_field(raw_text, "Version")
    effective_date = extract_field(raw_text, "Effective Date")

    db.upsert_document(document_id, file_path.name, title, version, effective_date, content_hash)
    db.delete_chunks_for_document(document_id)  # clear old chunks in case the doc changed

    chunk_count = 0
    for section_label, section_text in split_into_sections(raw_text):
        embedding = embed_text(section_text)
        db.insert_chunk(document_id, section_label, section_text, embedding)
        chunk_count += 1

    return IngestResult(document_id=document_id, file_name=file_path.name, status="ingested", chunks_created=chunk_count)


def ingest_from_manifest(manifest_path: Path, policies_dir: Path) -> list[IngestResult]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    for entry in manifest["documents"]:
        file_path = policies_dir / entry["file_name"]
        try:
            result = ingest_document(file_path, entry["document_id"])
        except (UnsupportedDocumentType, EmptyDocumentError) as e:
            result = IngestResult(document_id=entry["document_id"], file_name=entry["file_name"], status="failed", error=str(e))
        results.append(result)
    return results