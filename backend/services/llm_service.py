"""
LLM service — supports 3 providers via LLM_PROVIDER env var:

  LLM_PROVIDER=anthropic   → Claude API (default, paid)
  LLM_PROVIDER=groq        → Groq cloud  (free tier, fast)  ← recommended for hackathon
  LLM_PROVIDER=ollama      → Ollama local (100% free, needs local model)

Groq and Ollama both expose an OpenAI-compatible API, so we use the openai
package for them. Anthropic keeps its own client.
"""

import json
import os
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()

# --- Anthropic ---
if LLM_PROVIDER == "anthropic":
    import anthropic as _anthropic
    _anthropic_client = _anthropic.AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY", "")
    )
    MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

# --- Groq (OpenAI-compatible) ---
elif LLM_PROVIDER == "groq":
    from openai import AsyncOpenAI
    _openai_client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY", ""),
    )
    MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

# --- Ollama (OpenAI-compatible local) ---
elif LLM_PROVIDER == "ollama":
    from openai import AsyncOpenAI
    _openai_client = AsyncOpenAI(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",  # required by the openai client but ignored by ollama
    )
    MODEL = os.getenv("LLM_MODEL", "llama3.2")

else:
    raise ValueError(f"Unknown LLM_PROVIDER: '{LLM_PROVIDER}'. Use: anthropic | groq | ollama")


# ---------------------------------------------------------------------------
# Internal helper — one interface for all providers
# ---------------------------------------------------------------------------

def _strip_fences(raw: str) -> str:
    """Remove markdown ```json ... ``` code fences if present."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        # parts[1] is the content (may start with 'json\n')
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


async def _chat(system: str, user: str) -> str:
    """Send a system + user message and return the raw text response."""
    if LLM_PROVIDER == "anthropic":
        msg = await _anthropic_client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text

    else:  # groq or ollama — openai-compatible
        resp = await _openai_client.chat.completions.create(
            model=MODEL,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Agent 1 — Interview Parsing Agent
# ---------------------------------------------------------------------------

INTERVIEW_SYSTEM_PROMPT = """\
You are an AI recruitment signal extractor.

Your task is to analyze unstructured interview feedback and convert it into \
structured recruitment signals.

You must extract:
- strengths
- weaknesses
- risks
- motivation_signal  (one of: low, medium, high)
- psychological_signal  (one of: negative, mixed, positive, positive and engaged)
- summary

Rules:
- Use only the provided text.
- Do not invent information.
- Keep items concise (short phrases, not full sentences).
- Return ONLY valid JSON with the exact keys shown below, nothing else.

Expected JSON:
{
  "strengths": ["..."],
  "weaknesses": ["..."],
  "risks": ["..."],
  "motivation_signal": "medium",
  "psychological_signal": "positive",
  "summary": "..."
}
"""


async def extract_interview_signals(review_text: str) -> Dict[str, Any]:
    """Call the configured LLM to extract structured signals from raw interview text."""
    raw = await _chat(INTERVIEW_SYSTEM_PROMPT, review_text)
    return json.loads(_strip_fences(raw))


# ---------------------------------------------------------------------------
# Agent 2 — Final Synthesis Agent
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """\
You are an AI recruitment analyst.

You receive a fully processed candidate assessment object.
Your task is to generate a standardized candidate synthesis report.

Rules:
- Use only the provided structured evidence.
- Do not invent facts.
- Clearly distinguish strengths, weaknesses, and risks.
- decision must be one of: Hire, Consider, No Hire
- confidence_level must be one of: High, Medium, Low
- overall_score must be a float between 0.0 and 1.0
- domain_fit: 2-3 sentences describing in which specific job domains/roles this candidate would excel, \
which skills they can apply immediately, and the recommended role type.
- Return ONLY valid JSON with the exact keys shown below, nothing else.

Expected JSON:
{
  "executive_summary": "...",
  "decision": "Consider",
  "confidence_level": "Medium",
  "overall_score": 0.77,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "risks": ["..."],
  "technical_assessment": "...",
  "behavioral_assessment": "...",
  "consistency_analysis": "...",
  "justification": "...",
  "domain_fit": "Strong fit for Backend Development and DevOps roles. Can contribute immediately on CI/CD pipelines and API development. Recommended entry point: Junior Backend Engineer."
}
"""

# ---------------------------------------------------------------------------
# Agent 0 — Test Sheet Parsing Agent
# ---------------------------------------------------------------------------

TEST_PARSE_SYSTEM_PROMPT = """\
You are an AI technical test evaluator.

You receive the text content of a technical test sheet or evaluation form.
Your task is to extract the competencies that were evaluated and normalize the scores to a 1-5 scale.

Rules:
- Extract all evaluated competencies and their scores.
- Normalize scores to a 1-5 integer scale (1=weak, 2=insufficient, 3=acceptable, 4=good, 5=excellent).
- Group competency keys as: "technical.<skill>", "soft.<skill>", or "motivation.<skill>".
- target_skills: list of clean skill names (no prefix) found in the test.
- Return ONLY valid JSON with the exact keys shown below, nothing else.

Expected JSON:
{
  "scores": {
    "technical.python": 4,
    "soft.communication": 3,
    "motivation.role_interest": 5
  },
  "target_skills": ["Python", "Communication", "Role interest"]
}
"""


async def parse_test_sheet(file_text: str) -> Dict[str, Any]:
    """Call the configured LLM to extract structured scores from a test sheet."""
    raw = await _chat(TEST_PARSE_SYSTEM_PROMPT, file_text)
    return json.loads(_strip_fences(raw))


# ---------------------------------------------------------------------------
# Agent 0b — Candidate Name Extractor (bypasses HrFlow name parsing bugs)
# ---------------------------------------------------------------------------

NAME_EXTRACT_PROMPT = """\
You are a CV parser. Extract only the candidate's full name from the CV text below.

Rules:
- Return ONLY the full name as plain text (e.g. "Nabil Marc Chartouni").
- Correct capitalisation (First Last format).
- Do NOT return JSON, labels, or any other text — just the name.
- If you cannot determine the name, return an empty string.
"""


async def extract_candidate_name(cv_text: str) -> str:
    """Use the LLM to extract the candidate's full name from raw CV text."""
    # Only send the first 800 chars — the name is always near the top
    snippet = cv_text[:800].strip()
    if not snippet:
        return ""
    raw = await _chat(NAME_EXTRACT_PROMPT, snippet)
    return raw.strip()


async def generate_synthesis(assessment_object: Dict[str, Any]) -> Dict[str, Any]:
    """Call the configured LLM to generate the final candidate synthesis report."""
    payload = json.dumps(assessment_object, indent=2, ensure_ascii=False)
    raw = await _chat(SYNTHESIS_SYSTEM_PROMPT, payload)
    return json.loads(_strip_fences(raw))
