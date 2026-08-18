"""
Thin wrapper around the Gemini API for embeddings and generation.
Kept intentionally simple: no retries, no backoff — if a call fails,
it raises, and the route in main.py returns a clear error. That's
enough for a project this size; production systems would add retries,
but that's complexity we don't need to learn this concept.
"""
import json

from google import genai
from google.genai import types

from app.config import settings

_client = genai.Client(api_key=settings.google_api_key)


def embed_text(text: str) -> list[float]:
    result = _client.models.embed_content(model=settings.embedding_model, contents=text)
    return result.embeddings[0].values


ANSWER_PROMPT = """You are a policy Q&A assistant. Answer ONLY using the evidence below.
Do not use any outside knowledge, even if you're confident it's correct.

Rules:
1. If the evidence doesn't clearly support an answer, set "supported" to false.
2. Every citation must exactly match a (document_id, section) pair shown in the evidence.
   Do not invent sections or documents.
3. Distinguish mandatory rules ("must") from recommendations ("should") in your answer.
4. Respond with ONLY a JSON object, no markdown fences, matching exactly:

{{
  "answer": "<string>",
  "supported": <true|false>,
  "citations": [{{"document_id": "<id>", "section": "<section>"}}]
}}

Evidence:
{evidence}

Question: {question}
"""


def generate_answer_from_gemini(question: str, evidence_block: str) -> str:
    prompt = ANSWER_PROMPT.format(evidence=evidence_block, question=question)
    response = _client.models.generate_content(
        model=settings.generation_model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"),
    )
    return response.text


def parse_model_json(raw_text: str) -> dict | None:
    """Returns None instead of raising if the model's output isn't valid JSON —
    the graph node checks for None and refuses cleanly instead of crashing."""
    cleaned = raw_text.strip().strip("`")
    if cleaned.startswith("json"):
        cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None