import pytest

from app.ingest import (
    EmptyDocumentError,
    UnsupportedDocumentType,
    split_into_sections,
    sub_chunk_if_needed,
    _hash_content,
)


def test_split_into_sections_labels_correctly():
    text = """# Some Policy

## Section 1 — Purpose
Body one.

## Section 2 — Rules
Body two, more text.
"""
    sections = split_into_sections(text)
    assert len(sections) == 2
    assert sections[0][0] == "Section 1 — Purpose"
    assert "Body one." in sections[0][1]
    assert sections[1][0] == "Section 2 — Rules"


def test_split_into_sections_handles_document_with_no_headers():
    text = "Just some plain text with no section markers."
    sections = split_into_sections(text)
    assert len(sections) == 1
    assert sections[0][0] == "Full Document"


def test_sub_chunk_preserves_section_label_when_splitting_long_section():
    long_body = "\n".join([f"Paragraph {i} " + ("word " * 50) for i in range(10)])
    chunks = sub_chunk_if_needed("Section 5 — Long", long_body, max_words=100)
    assert len(chunks) > 1
    assert all(label == "Section 5 — Long" for label, _ in chunks)


def test_sub_chunk_returns_single_chunk_when_under_limit():
    body = "A short section body."
    chunks = sub_chunk_if_needed("Section 1", body, max_words=300)
    assert len(chunks) == 1


def test_hash_content_is_deterministic():
    text = "some policy text"
    assert _hash_content(text) == _hash_content(text)


def test_hash_content_differs_for_different_text():
    assert _hash_content("a") != _hash_content("b")


def test_ingest_document_rejects_unsupported_extension(tmp_path):
    from app.ingest import ingest_document

    bad_file = tmp_path / "policy.pdf"
    bad_file.write_bytes(b"%PDF-1.4 fake content")

    with pytest.raises(UnsupportedDocumentType):
        ingest_document(bad_file, "POL-999")


def test_ingest_document_rejects_empty_file(tmp_path, monkeypatch):
    from app.ingest import ingest_document
    import app.db as db

    monkeypatch.setattr(db, "get_document_hash", lambda doc_id: None)

    empty_file = tmp_path / "empty.md"
    empty_file.write_text("   \n\n  ")

    with pytest.raises(EmptyDocumentError):
        ingest_document(empty_file, "POL-998")


def test_duplicate_ingestion_is_skipped(tmp_path, monkeypatch):
    from app.ingest import ingest_document, _hash_content
    import app.db as db

    content = "# Test Policy\n\n**Version:** 1.0\n**Effective Date:** 2026-01-01\n\n## Section 1 — X\nBody."
    f = tmp_path / "test.md"
    f.write_text(content)

    monkeypatch.setattr(db, "get_document_hash", lambda doc_id: _hash_content(content))

    result = ingest_document(f, "POL-DUP")
    assert result.status == "skipped_duplicate"
