"""
The LangGraph pipeline: retrieve -> generate_answer -> validate_citations.

Each "node" is just a normal Python function that takes the current state
(a dict) and returns an updated state. LangGraph's only job is to run them
in order and pass the state along. That's it — no magic, no branching,
no loops. If this were plain Python instead of LangGraph, it would look
almost identical, just without the graph.add_node/add_edge wiring below.
"""
from typing import TypedDict

from langgraph.graph import StateGraph, END

from app import db
from app.config import settings
from app.llm import embed_text, generate_answer_from_gemini, parse_model_json
from app.schemas import AnswerResponse, Citation, RefusalReason, RetrievedChunk


class GraphState(TypedDict, total=False):
    question: str
    top_k: int
    retrieved_chunks: list[RetrievedChunk]
    raw_model_output: str
    final_context: str
    answer: AnswerResponse


# ---------------------------------------------------------------------------
# Node 1: retrieve — turn the question into an embedding, search the local store
# ---------------------------------------------------------------------------
def node_retrieve(state: GraphState) -> GraphState:
    question_embedding = embed_text(state["question"])
    top_k = state.get("top_k") or settings.default_top_k

    rows = db.similarity_search(question_embedding, top_k)
    state["retrieved_chunks"] = [
        RetrievedChunk(document_id=r[0], document_title=r[1], section=r[2], text=r[3], score=float(r[4]))
        for r in rows
    ]
    return state


# ---------------------------------------------------------------------------
# Node 2: generate_answer — ask Gemini to answer using only the retrieved text
# ---------------------------------------------------------------------------
def node_generate_answer(state: GraphState) -> GraphState:
    chunks = state.get("retrieved_chunks", [])

    # Nothing relevant retrieved -> refuse immediately, don't waste an API call
    if not chunks or chunks[0].score < settings.similarity_threshold:
        state["answer"] = AnswerResponse(
            answer="I don't have sufficient evidence in the policy documents to answer this question.",
            supported=False,
            confidence=chunks[0].score if chunks else 0.0,
            reason_for_refusal=RefusalReason.NO_RELEVANT_EVIDENCE,
        )
        return state

    # Build a simple evidence block: one paragraph per chunk, labeled with its source
    evidence_block = "\n\n".join(
        f"[document_id: {c.document_id} | section: {c.section}]\n{c.text}" for c in chunks
    )
    state["final_context"] = evidence_block

    raw_output = generate_answer_from_gemini(state["question"], evidence_block)
    state["raw_model_output"] = raw_output

    parsed = parse_model_json(raw_output)
    if parsed is None:
        # Model didn't return valid JSON — refuse rather than guess
        state["answer"] = AnswerResponse(
            answer="The model produced a response that could not be understood.",
            supported=False,
            retrieved_sources=chunks,
            confidence=chunks[0].score,
            reason_for_refusal=RefusalReason.GENERATION_ERROR,
        )
        return state

    citations = [
        Citation(
            document_id=c["document_id"],
            document_title=next((rc.document_title for rc in chunks if rc.document_id == c["document_id"]), c["document_id"]),
            section=c["section"],
        )
        for c in parsed.get("citations", [])
    ]

    state["answer"] = AnswerResponse(
        answer=parsed.get("answer", ""),
        supported=bool(parsed.get("supported", False)),
        citations=citations,
        retrieved_sources=chunks,
        confidence=chunks[0].score,
    )
    return state


# ---------------------------------------------------------------------------
# Node 3: validate_citations — a plain check, not an LLM call. Makes sure the
# model didn't cite a document/section it wasn't actually given.
# ---------------------------------------------------------------------------
def node_validate_citations(state: GraphState) -> GraphState:
    answer = state["answer"]
    if not answer.supported:
        return state  # already refused, nothing to check

    if not answer.citations:
        state["answer"] = answer.model_copy(update={
            "supported": False,
            "reason_for_refusal": RefusalReason.MISSING_CITATION,
        })
        return state

    retrieved_keys = {(c.document_id, c.section) for c in state.get("retrieved_chunks", [])}
    for citation in answer.citations:
        if (citation.document_id, citation.section) not in retrieved_keys:
            state["answer"] = answer.model_copy(update={
                "supported": False,
                "reason_for_refusal": RefusalReason.CITATION_MISMATCH,
            })
            return state

    return state


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("retrieve", node_retrieve)
    graph.add_node("generate_answer", node_generate_answer)
    graph.add_node("validate_citations", node_validate_citations)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate_answer")
    graph.add_edge("generate_answer", "validate_citations")
    graph.add_edge("validate_citations", END)

    return graph.compile()


answer_graph = build_graph()


def run_question(question: str, top_k: int | None = None) -> GraphState:
    return answer_graph.invoke({"question": question, "top_k": top_k or settings.default_top_k})