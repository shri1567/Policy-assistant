from app.graph import node_validate_citations
from app.schemas import AnswerResponse, Citation, RefusalReason, RetrievedChunk


def _chunk(doc_id="POL-001", section="Section 2"):
    return RetrievedChunk(
        document_id=doc_id, document_title="Leave Policy", section=section,
        text="Some evidence text.", score=0.8,
    )


def test_validate_citations_passes_when_citation_matches_retrieved_chunk():
    chunks = [_chunk()]
    answer = AnswerResponse(
        answer="You accrue 1.75 days/month.",
        supported=True,
        citations=[Citation(document_id="POL-001", document_title="Leave Policy", section="Section 2")],
        retrieved_sources=chunks,
        confidence=0.8,
    )
    state = {"answer": answer, "retrieved_chunks": chunks}
    result = node_validate_citations(state)
    assert result["answer"].supported is True


def test_validate_citations_flags_mismatch_citation():
    chunks = [_chunk(section="Section 2")]
    answer = AnswerResponse(
        answer="Some answer",
        supported=True,
        citations=[Citation(document_id="POL-001", document_title="Leave Policy", section="Section 9")],
        retrieved_sources=chunks,
        confidence=0.8,
    )
    state = {"answer": answer, "retrieved_chunks": chunks}
    result = node_validate_citations(state)
    assert result["answer"].supported is False
    assert result["answer"].reason_for_refusal == RefusalReason.CITATION_MISMATCH


def test_validate_citations_flags_missing_citation_when_supported_true():
    chunks = [_chunk()]
    answer = AnswerResponse(
        answer="Some answer with no citation",
        supported=True,
        citations=[],
        retrieved_sources=chunks,
        confidence=0.8,
    )
    state = {"answer": answer, "retrieved_chunks": chunks}
    result = node_validate_citations(state)
    assert result["answer"].supported is False
    assert result["answer"].reason_for_refusal == RefusalReason.MISSING_CITATION


def test_validate_citations_skips_check_when_already_refused():
    answer = AnswerResponse(
        answer="No evidence found.",
        supported=False,
        citations=[],
        retrieved_sources=[],
        confidence=0.0,
        reason_for_refusal=RefusalReason.NO_RELEVANT_EVIDENCE,
    )
    state = {"answer": answer, "retrieved_chunks": []}
    result = node_validate_citations(state)
    assert result["answer"].reason_for_refusal == RefusalReason.NO_RELEVANT_EVIDENCE
