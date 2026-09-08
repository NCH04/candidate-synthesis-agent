"""
LLM service — Anthropic Claude only.

Cost-aware model routing:
  * FAST model  (Haiku)  → cheap, structured extraction (CV parse, interview
                           signals, test-sheet parsing). ~5x cheaper.
  * SMART model (Sonnet) → reasoning-heavy work (profile scoring, synthesis,
                           critic pass, fairness review).

Both are env-overridable (CLAUDE_MODEL_FAST / CLAUDE_MODEL_SMART).

Every agent returns JSON. `_json_chat` parses it and, when a Pydantic model is
supplied, validates the shape. On a parse/validation failure it retries once
with the error fed back to the model, then raises `LLMOutputError`. Without
that, a hallucinated shape propagated silently to the UI.

Note on prompt caching: the system prompts here are short (a few hundred
tokens), below Anthropic's minimum cacheable prefix (model-dependent,
512-4096 tokens). Ephemeral caching would therefore not trigger, so it is
intentionally not used — the cost wins come from model routing, dropping
redundant calls, deterministic pre-filters, and result caching instead.
"""

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

try:
    from ..schemas import (
        CandidateSynthesisReport,
        CVProfile,
        ExtractedInterviewSignals,
        FairnessReport,
        ProfileJobScore,
        TestSheetParseResult,
    )
except ImportError:  # running with `backend/` as the root (native dev)
    from schemas import (  # type: ignore
        CandidateSynthesisReport,
        CVProfile,
        ExtractedInterviewSignals,
        FairnessReport,
        ProfileJobScore,
        TestSheetParseResult,
    )

# ---------------------------------------------------------------------------
# Client + model tiers
# ---------------------------------------------------------------------------

_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

# Cheap model for simple structured extraction
FAST_MODEL = os.getenv("CLAUDE_MODEL_FAST", "claude-haiku-4-5")
# Smarter model for reasoning-heavy steps.
# claude-sonnet-5 supersedes claude-sonnet-4-6 and is cheaper ($2/$10 per MTok
# vs $3/$15), so it is the default on both counts.
SMART_MODEL = os.getenv("CLAUDE_MODEL_SMART", "claude-sonnet-5")

# Back-compat: a single override applies to the smart tier
if os.getenv("CLAUDE_MODEL"):
    SMART_MODEL = os.environ["CLAUDE_MODEL"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class LLMOutputError(RuntimeError):
    """The model returned something that is not the JSON shape we asked for."""


def strip_fences(raw: str) -> str:
    """Remove markdown ```json ... ``` code fences if present."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) > 1:
            raw = parts[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    return raw.strip()


def parse_json_response(raw: str) -> Any:
    """Parse a model response that is expected to be a JSON document.

    Tolerates code fences and stray prose around the JSON body.
    """
    text = strip_fences(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost {...} / [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMOutputError(f"Model did not return valid JSON (got {text[:200]!r})")


def _text_of(msg: Any) -> str:
    """Concatenate every text block of a response.

    Reading `content[0].text` breaks as soon as the first block is not text
    (a thinking block, for instance), which is exactly what happens if the
    model tier is ever switched to a thinking-enabled one.
    """
    return "".join(
        block.text for block in msg.content if getattr(block, "type", None) == "text"
    ).strip()


async def _chat(system: str, user: str, *, model: str, max_tokens: int = 2048) -> str:
    """Send a system + user message and return the raw text response."""
    msg = await _client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return _text_of(msg)


async def _json_chat(
    system: str,
    user: str,
    *,
    model: str,
    max_tokens: int = 2048,
    schema: type[BaseModel] | None = None,
) -> dict[str, Any]:
    """Call the model, parse JSON, optionally validate, retry once on failure.

    The retry appends the parse/validation error to the user message so the
    model can correct itself rather than reproducing the same broken output.
    """
    attempt_user = user
    last_error: Exception | None = None

    for attempt in range(2):
        raw = await _chat(system, attempt_user, model=model, max_tokens=max_tokens)
        try:
            data = parse_json_response(raw)
            if schema is not None:
                # Validate, then hand back the *raw* dict: downstream agents and
                # the frontend consume plain JSON, and dropping unknown keys here
                # would silently discard fields the prompt asked for.
                schema.model_validate(data)
            if not isinstance(data, dict):
                raise LLMOutputError(f"Expected a JSON object, got {type(data).__name__}")
            return data
        except (LLMOutputError, ValidationError) as exc:
            last_error = exc
            if attempt == 0:
                attempt_user = (
                    f"{user}\n\n---\nYour previous answer was rejected: {exc}\n"
                    "Return ONLY the valid JSON object described in the system prompt, "
                    "with no prose and no code fences."
                )

    raise LLMOutputError(f"Model output invalid after a retry: {last_error}")


async def _chat_stream(
    system: str, user: str, *, model: str, max_tokens: int = 2048
) -> AsyncIterator[str]:
    """Stream a system + user message, yielding text deltas as they arrive."""
    async with _client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


# ---------------------------------------------------------------------------
# Agent — Interview Signal Extractor  (FAST)
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


async def extract_interview_signals(review_text: str) -> dict[str, Any]:
    """Call Claude (fast tier) to extract structured signals from interview text."""
    return await _json_chat(
        INTERVIEW_SYSTEM_PROMPT,
        review_text,
        model=FAST_MODEL,
        schema=ExtractedInterviewSignals,
    )


# ---------------------------------------------------------------------------
# Agent — Test Sheet Parser  (FAST, used only as a fallback to the regex parser)
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


async def parse_test_sheet(file_text: str) -> dict[str, Any]:
    """Call Claude (fast tier) to extract structured scores from a test sheet."""
    return await _json_chat(
        TEST_PARSE_SYSTEM_PROMPT,
        file_text,
        model=FAST_MODEL,
        schema=TestSheetParseResult,
    )


# ---------------------------------------------------------------------------
# Agent — CV Structure Extractor  (FAST)
# ---------------------------------------------------------------------------

CV_PARSE_SYSTEM_PROMPT = """\
You are an AI CV parser.

You receive the raw text of a candidate's CV (extracted from a PDF).
Your task is to extract a structured profile.

Rules:
- Use only information present in the text.
- Do not invent or infer beyond what is written.
- full_name: the candidate's full name, correctly capitalised (First Last).
- skills: concrete technical and soft skills, no duplicates, normalized capitalisation.
- experiences: most relevant professional/project experiences with title, company/context, duration, summary.
- education: degree, institution, year if present.
- summary: 2-3 sentences neutral description of the candidate profile.
- Return ONLY valid JSON with the exact keys shown below, nothing else.

Expected JSON:
{
  "full_name": "Jane Smith",
  "skills": ["Python", "FastAPI", "Docker", "Team leadership"],
  "experiences": [
    {"title": "Backend Engineer", "context": "ACME Corp", "duration": "2022-2024", "summary": "Built REST APIs and CI/CD pipelines"}
  ],
  "education": [
    {"degree": "MSc Computer Science", "institution": "University X", "year": "2022"}
  ],
  "summary": "Junior backend engineer with 2 years of experience in Python and cloud infrastructure."
}
"""


async def parse_cv_structure(cv_text: str) -> dict[str, Any]:
    """Use Claude (fast tier) to extract a structured profile from raw CV text.

    This single call also returns full_name — there is no separate
    name-extraction request (that would be a redundant round-trip).
    """
    return await _json_chat(
        CV_PARSE_SYSTEM_PROMPT,
        cv_text[:8000],
        model=FAST_MODEL,
        schema=CVProfile,
    )


# ---------------------------------------------------------------------------
# Agent — Profile / Job Fit Scorer  (SMART)
# ---------------------------------------------------------------------------

SCORE_SYSTEM_PROMPT = """\
You are an AI recruitment scoring agent.

You receive a structured candidate profile and a job description (title + required skills + summary).
Your task is to evaluate the candidate-job fit.

Rules:
- score: integer 0-100 where 0=no fit and 100=perfect fit.
- experience_fit: one short sentence describing how the candidate's experience matches the role.
- summary: 1-2 sentences explaining the score.
- Consider: matched skills coverage, experience relevance, education alignment.
- Return ONLY valid JSON with the exact keys shown below, nothing else.

Expected JSON:
{
  "score": 72,
  "experience_fit": "Backend Engineer experience aligns well with the Junior Backend Engineer role.",
  "summary": "Strong technical alignment with the required Python and API skills; experience level matches a junior position."
}
"""


async def score_profile_job(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """Use Claude (smart tier) to score a candidate profile against a job description."""
    payload = json.dumps({"profile": profile, "job": job}, indent=2, ensure_ascii=False)
    return await _json_chat(
        SCORE_SYSTEM_PROMPT,
        payload,
        model=SMART_MODEL,
        max_tokens=512,
        schema=ProfileJobScore,
    )


# ---------------------------------------------------------------------------
# Agent — Final Synthesis (draft pass)  (SMART)
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """\
You are an AI recruitment analyst.

You receive a fully processed candidate assessment object containing:
- CV/profile matching evidence
- Test scores (technical, soft, motivation)
- Interview signals (strengths, weaknesses, risks, motivation, psychological signal)

Your task is to generate a standardized candidate synthesis report.

Rules:
- Use only the provided structured evidence.
- Do not invent facts.
- Every item in strengths/weaknesses/risks MUST include a citation pointing to the source extract.
- Clearly distinguish strengths, weaknesses, and risks.
- decision must be one of: Hire, Consider, No Hire
- confidence_level must be one of: High, Medium, Low
- overall_score must be a float between 0.0 and 1.0
- domain_fit: 2-3 sentences describing in which specific job domains/roles this candidate would excel.
- Return ONLY valid JSON with the exact keys shown below, nothing else.

A citation object has the shape:
  { "source": "cv" | "test" | "interview", "extract": "<short verbatim or paraphrased snippet from the source>" }

Expected JSON:
{
  "executive_summary": "...",
  "decision": "Consider",
  "confidence_level": "Medium",
  "overall_score": 0.77,
  "strengths": [
    { "text": "Strong Python proficiency", "citation": { "source": "test", "extract": "technical.python: 4/5" } }
  ],
  "weaknesses": [
    { "text": "Limited system design experience", "citation": { "source": "interview", "extract": "lacks depth in system design" } }
  ],
  "risks": [
    { "text": "Junior level for senior responsibilities", "citation": { "source": "cv", "extract": "2 years of professional experience" } }
  ],
  "technical_assessment": "...",
  "behavioral_assessment": "...",
  "consistency_analysis": "...",
  "justification": "...",
  "domain_fit": "Strong fit for Backend Development and DevOps roles."
}
"""


async def generate_synthesis(assessment_object: dict[str, Any]) -> dict[str, Any]:
    """Call Claude (smart tier) to generate the draft synthesis report (with citations)."""
    payload = json.dumps(assessment_object, indent=2, ensure_ascii=False)
    return await _json_chat(
        SYNTHESIS_SYSTEM_PROMPT,
        payload,
        model=SMART_MODEL,
        max_tokens=3072,
        schema=CandidateSynthesisReport,
    )


# ---------------------------------------------------------------------------
# Agent — Synthesis Critic (multi-pass step 2)  (SMART)
# ---------------------------------------------------------------------------

CRITIC_SYSTEM_PROMPT = """\
You are an AI synthesis critic.

You receive:
1. The original structured candidate assessment object (the evidence).
2. A draft synthesis report produced by another agent.

Your task is to spot problems in the draft and produce a corrected, final version.

Check for:
- Claims not supported by the provided evidence.
- Internal inconsistencies (e.g. positive strengths contradicting a "No Hire" decision).
- Weak or generic justifications.
- Missing or vague citations.
- Decision / confidence_level / overall_score not aligned with the evidence.

Rules:
- Output the SAME JSON shape as the draft, but corrected.
- Keep items that are well supported.
- Fix wording, sharpen justifications, fix decision/score if the evidence demands it.
- Every strength/weakness/risk must still carry a citation.
- Return ONLY the corrected valid JSON, nothing else.
"""


async def critique_and_refine_synthesis(
    assessment_object: dict[str, Any],
    draft_report: dict[str, Any],
) -> dict[str, Any]:
    """Run Claude (smart tier) as a critic on the draft synthesis; return the refined version."""
    payload = json.dumps(
        {"evidence": assessment_object, "draft_report": draft_report},
        indent=2,
        ensure_ascii=False,
    )
    return await _json_chat(
        CRITIC_SYSTEM_PROMPT,
        payload,
        model=SMART_MODEL,
        max_tokens=3072,
        schema=CandidateSynthesisReport,
    )


# ---------------------------------------------------------------------------
# Agent — Fairness / Bias Check  (SMART, only invoked when the cheap
# deterministic pre-filter finds a candidate term — see fairness_service.py)
# ---------------------------------------------------------------------------

FAIRNESS_SYSTEM_PROMPT = """\
You are an AI fairness reviewer for recruitment outputs.

You receive a final candidate synthesis report.
Your task is to flag any potentially discriminatory, biased, or non-job-relevant content.

Look for:
- References to age, gender, ethnicity, nationality, religion, family status, health.
- Bias by prestige (school/company name used as a proxy instead of demonstrated skill).
- Personality judgments not grounded in the evidence.
- Language that could constitute illegal discrimination in EU/US recruitment contexts.

Rules:
- If everything is fine, return: { "status": "ok", "flags": [] }.
- Otherwise, for each issue, return an object: { "field": "<field path>", "issue": "<short reason>", "suggestion": "<reformulation>" }.
- Be precise — do NOT flag legitimate skill-based statements.
- Return ONLY valid JSON with the exact keys shown below, nothing else.

Expected JSON:
{
  "status": "ok" | "flagged",
  "flags": [
    { "field": "strengths[0].text", "issue": "References candidate's age", "suggestion": "Replace with skill-based statement" }
  ]
}
"""


async def fairness_check(synthesis_report: dict[str, Any]) -> dict[str, Any]:
    """Run Claude (smart tier) as a fairness reviewer on the final synthesis report."""
    payload = json.dumps(synthesis_report, indent=2, ensure_ascii=False)
    return await _json_chat(
        FAIRNESS_SYSTEM_PROMPT,
        payload,
        model=SMART_MODEL,
        max_tokens=1024,
        schema=FairnessReport,
    )


# ---------------------------------------------------------------------------
# Streaming variant of the synthesis (for the live results page)  (SMART)
# ---------------------------------------------------------------------------

async def generate_synthesis_stream(assessment_object: dict[str, Any]) -> AsyncIterator[str]:
    """Stream the draft synthesis report token by token (for SSE)."""
    payload = json.dumps(assessment_object, indent=2, ensure_ascii=False)
    async for delta in _chat_stream(
        SYNTHESIS_SYSTEM_PROMPT, payload, model=SMART_MODEL, max_tokens=3072
    ):
        yield delta
