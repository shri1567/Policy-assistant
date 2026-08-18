"""
Runs the eval question set against the live graph and reports the metrics
required in Section 7 of the project spec. Run with:
    uv run python -m app.evaluate
"""
import json
from pathlib import Path

from app.graph import run_question

EVAL_PATH = Path(__file__).resolve().parent.parent / "data" / "eval" / "eval_questions.json"


def run_evaluation():
    eval_set = json.loads(EVAL_PATH.read_text(encoding="utf-8"))["questions"]

    total = len(eval_set)
    retrieval_hits = 0          # expected document actually shows up in retrieved_sources
    citation_correct = 0        # for questions that should be answered, citation matches expected doc
    supported_correct = 0       # supported/refused matches expectation
    unsupported_total = 0
    unsupported_refused = 0
    unsupported_claims = 0      # supported=True but no valid citation (shouldn't happen post-validation, tracked anyway)

    detailed_results = []

    for q in eval_set:
        state = run_question(q["question"])
        answer = state["answer"]
        expected_should_answer = q["should_answer"]
        expected_docs = [d.strip() for d in q["expected_source_document"].split(",")] if q["expected_source_document"] != "none" else []

        retrieved_doc_ids = {c.document_id for c in state.get("retrieved_chunks", [])}
        hit = bool(set(expected_docs) & retrieved_doc_ids) if expected_docs else (len(retrieved_doc_ids) == 0 or True)
        if expected_docs:
            retrieval_hits += int(hit)

        matches_expectation = answer.supported == expected_should_answer
        supported_correct += int(matches_expectation)

        if not expected_should_answer:
            unsupported_total += 1
            unsupported_refused += int(not answer.supported)

        if expected_should_answer and answer.supported:
            cited_docs = {c.document_id for c in answer.citations}
            if cited_docs & set(expected_docs):
                citation_correct += 1
            if not answer.citations:
                unsupported_claims += 1

        detailed_results.append({
            "question_id": q["question_id"],
            "type": q["type"],
            "expected_should_answer": expected_should_answer,
            "actual_supported": answer.supported,
            "matches_expectation": matches_expectation,
            "reason_for_refusal": answer.reason_for_refusal,
        })

    supported_expected_count = sum(1 for q in eval_set if q["should_answer"])

    report = {
        "total_questions": total,
        "retrieval_hit_rate": round(retrieval_hits / max(1, len([q for q in eval_set if q["expected_source_document"] != "none"])), 3),
        "citation_correctness": round(citation_correct / max(1, supported_expected_count), 3),
        "supported_answer_accuracy": round(supported_correct / total, 3),
        "unsupported_question_refusal_rate": round(unsupported_refused / max(1, unsupported_total), 3),
        "answers_with_unsupported_claims": unsupported_claims,
        "details": detailed_results,
    }
    return report


if __name__ == "__main__":
    report = run_evaluation()
    print(json.dumps(report, indent=2, default=str))
