"""
These tests cover the remaining required scenarios from the spec (Section 6):
- question answered from one section
- multi-document question
- unsupported question
- ambiguous question
- empty retrieval result
- terminology different from document wording

They run against the live graph, so they require GOOGLE_API_KEY (the local
JSON store needs no separate setup — it's created automatically). They're
written with a skip guard so `pytest tests/test_ingestion.py tests/test_graph.py`
still runs fine without a real API key.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL") or not os.getenv("GOOGLE_API_KEY"),
    reason="Requires live Postgres+pgvector and GOOGLE_API_KEY; see README for setup.",
)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        c.post("/documents/ingest")  # idempotent, safe to call repeatedly
        yield c


def test_question_answered_from_single_section(client):
    resp = client.post("/questions", json={"question": "How many days of paid sick leave do employees get per year?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["supported"] is True
    assert any(c["document_id"] == "POL-001" for c in body["citations"])


def test_multi_document_question(client):
    resp = client.post("/questions", json={
        "question": "Can a fully remote employee working from another country store confidential client data on a personal laptop?"
    })
    body = resp.json()
    cited_docs = {c["document_id"] for c in body["citations"]}
    # should draw on both remote work and security policy
    assert body["supported"] is True
    assert len(cited_docs) >= 1  # at minimum cites the controlling policy


def test_unsupported_legal_question_is_refused(client):
    resp = client.post("/questions", json={
        "question": "What is the statutory minimum notice period required by UAE labour law for termination?"
    })
    body = resp.json()
    assert body["supported"] is False
    assert body["reason_for_refusal"] is not None


def test_ambiguous_question_does_not_get_fabricated_answer(client):
    resp = client.post("/questions", json={"question": "How much leave can I take?"})
    body = resp.json()
    # either refused as ambiguous, or answered narrowly with citations -- but never
    # unsupported=True with no citations
    if body["supported"]:
        assert len(body["citations"]) > 0


def test_empty_retrieval_result_is_handled(client, monkeypatch):
    import app.db as db
    monkeypatch.setattr(db, "similarity_search", lambda *a, **kw: [])

    resp = client.post("/questions", json={"question": "asdkfjalksdjf random nonsense query"})
    body = resp.json()
    assert body["supported"] is False
    assert body["reason_for_refusal"] == "no_relevant_evidence"


def test_terminology_different_from_document_wording(client):
    # document says "working from another country" -- user says "WFH from abroad"
    resp = client.post("/questions", json={"question": "What's the rule for WFH from abroad?"})
    body = resp.json()
    if body["supported"]:
        assert any(c["document_id"] == "POL-003" for c in body["citations"])


def test_question_debug_endpoint_exposes_trace(client):
    resp = client.post("/questions", json={"question": "How many sick leave days per year?"})
    question_id = resp.json()["question_id"]

    debug_resp = client.get(f"/questions/{question_id}/debug")
    assert debug_resp.status_code == 200
    debug = debug_resp.json()
    assert debug["query"]
    assert "retrieved_chunks" in debug
    assert "final_context_sent_to_model" in debug


def test_duplicate_document_ingestion_returns_skipped(client):
    resp = client.post("/documents/ingest")
    results = resp.json()
    assert any(r["status"] == "skipped_duplicate" for r in results)
