# AGENTS.md

## Graph: `answer_graph`

Three nodes, linear flow, no cycles (this doesn't need agentic looping — it needs
deterministic, auditable behavior, which is why the citation check is a plain
Python node and not another LLM call).

```
retrieve → generate_answer → validate_citations → END
```

### Node: `retrieve`
- Input: `question: str`
- Embeds the question via Gemini (`gemini-embedding-001`), then compares it against
  every stored chunk in `data/store.json` using cosine similarity computed by hand
  in `app/db.py` (`top_k` configurable, default 6)
- Output: `retrieved_chunks: list[RetrievedChunk]` (each with doc_id, section, text, score)
- Does NOT decide refusal — that's downstream, because "no chunks above threshold"
  and "chunks retrieved but insufficient to answer" are different failure reasons
  that the eval report (Section 7 of requirements) needs to distinguish.

### Node: `generate_answer`
- Input: question + retrieved_chunks
- Prompts Gemini (`gemini-3.6-flash`) with a strict evidence-only instruction — the
  full prompt lives inline in `app/llm.py` as the `ANSWER_PROMPT` constant, not in a
  separate file
- Model is instructed to return structured JSON: `{answer, supported, citations}`
- If retrieval returned zero chunks or the top score is below `SIMILARITY_THRESHOLD`,
  this node short-circuits and does NOT call the LLM at all — returns a refusal
  directly. Saves an API call and guarantees refusal on empty evidence rather
  than trusting the model to refuse correctly every time.
- If the model's response isn't valid JSON, `parse_model_json()` returns `None`
  instead of raising, and this node refuses cleanly with `reason_for_refusal:
  "generation_error"` rather than crashing the request.

### Node: `validate_citations`
- Deterministic, no LLM call.
- Cross-checks every `(document_id, section)` pair in the model's `citations`
  against the actual `retrieved_chunks` set.
- Any citation not found in retrieved evidence → whole answer downgraded to
  `supported: false`, `reason_for_refusal: "citation_mismatch"`.
- Empty citations list with `supported: true` → downgraded the same way,
  `reason_for_refusal: "missing_citation"`.

## Why not more agentic (e.g. multi-hop retrieval, re-query loops)?
The requirements ask for traceable, reproducible evaluation (Section 7) with a
fixed set of ~20 questions. A loopy agent that re-queries an unbounded number
of times makes retrieval-debug output (Section 4.5) harder to reason about and
harder to grade against the evaluator file. Linear graph = every run produces
exactly one debug trace with a fixed shape.

If this grows past the project scope (e.g. genuinely multi-document reasoning
questions), the natural extension is a conditional edge from `retrieve` back
to itself once, capped, if the first retrieval score is below threshold but a
query-rewrite could plausibly help. Not implemented here — noted as a
"Not Doing" in SPEC.md territory, but calling it out here since it's the
obvious next agentic step.
In practice, the multi-document questions in this project's eval set were fixed
without needing a re-query loop at all — just widening `top_k` from 4 to 6 gave
the retrieve step enough breadth to surface evidence from two policies in one
pass. Worth trying the simple fix (retrieval width) before reaching for a more
complex agentic one (re-querying).