"""
LLM service — Anthropic Claude only.

All AI agents in the pipeline (CV parsing, interview signal extraction,
test sheet parsing, multi-pass synthesis, fairness check) go through
this single client.
"""

import json
import os
from typing import Any, AsyncIterator, Dict

import anthropic

# ---------------------------------------------------------------------------
# Client config
# ---------------------------------------------------------------------------

_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_fences(raw: str) -> str:
    """Remove markdown ```json ... ``` code fences if present."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


async def _chat(system: str, user: str, max_tokens: int = 2048) -> str:
    """Send a system + user message and return the raw text response."""
    msg = await _client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


async def _chat_stream(system: str, user: str, max_tokens: int = 2048) -> AsyncIterator[str]:
    """Stream a system + user message, yielding text deltas as they arrive."""
    async with _client.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


# ---------------------------------------------------------------------------
# Agent — Candidate Name Extractor
# ---------------------------------------------------------------------------

NAME_EXTRACT_PROMPT = """\
You are a CV parser. Extract only the candidate's full name from the CV text below.

Rules:
- Return ONLY the full name as plain text (e.g. "Jane Smith").
- Correct capitalisation (First Last format).
- Do NOT return JSON, labels, or any other text — just the name.
- If you cannot determine the name, return an empty string.
"""


async def extract_candidate_name(cv_text: str) -> str:
    """Use Claude to extract the candidate's full name from raw CV text."""
    snippet = cv_text[:800].strip()
    if not snippet:
        return ""
    raw = await _chat(NAME_EXTRACT_PROMPT, snippet, max_tokens=64)
    return raw.strip()


# ---------------------------------------------------------------------------
# Agent — Interview Signal Extractor
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
    """Call Claude to extract structured signals from raw interview text."""
    raw = await _chat(INTERVIEW_SYSTEM_PROMPT, review_text)
    return json.loads(_strip_fences(raw))


# ---------------------------------------------------------------------------
# Agent — Test Sheet Parser
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
    """Call Claude to extract structured scores from a test sheet."""
    raw = await _chat(TEST_PARSE_SYSTEM_PROMPT, file_text)
    return json.loads(_strip_fences(raw))


# ---------------------------------------------------------------------------
# Agent — CV Structure Extractor
# ---------------------------------------------------------------------------

CV_PARSE_SYSTEM_PROMPT = """\
You are an AI CV parser.

You receive the raw text of a candidate's CV (extracted from a PDF).
Your task is to extract a structured profile.

Rules:
- Use only information present in the text.
- Do not invent or infer beyond what is written.
- Skills: concrete technical and soft skills, no duplicates, normalized capitalisation.
- Experiences: most relevant professional/project experiences with title, company/context, duration, summary.
- Education: degree, institution, year if present.
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


async def parse_cv_structure(cv_text: str) -> Dict[str, Any]:
    """Use Claude to extract a structured profile from raw CV text."""
    raw = await _chat(CV_PARSE_SYSTEM_PROMPT, cv_text[:8000], max_tokens=2048)
    return json.loads(_strip_fences(raw))


# ---------------------------------------------------------------------------
# Agent — Profile / Job Fit Scorer
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


async def score_profile_job(profile: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    """Use Claude to score a candidate profile against a job description."""
    payload = json.dumps({"profile": profile, "job": job}, indent=2, ensure_ascii=False)
    raw = await _chat(SCORE_SYSTEM_PROMPT, payload, max_tokens=512)
    return json.loads(_strip_fences(raw))


# ---------------------------------------------------------------------------
# Agent — Final Synthesis (draft pass)
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


async def generate_synthesis(assessment_object: Dict[str, Any]) -> Dict[str, Any]:
    """Call Claude to generate the draft candidate synthesis report (with citations)."""
    payload = json.dumps(assessment_object, indent=2, ensure_ascii=False)
    raw = await _chat(SYNTHESIS_SYSTEM_PROMPT, payload, max_tokens=3072)
    return json.loads(_strip_fences(raw))


# ---------------------------------------------------------------------------
# Agent — Synthesis Critic (multi-pass step 2)
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
    assessment_object: Dict[str, Any],
    draft_report: Dict[str, Any],
) -> Dict[str, Any]:
    """Run Claude as a critic on the draft synthesis and return the refined version."""
    payload = json.dumps(
        {"evidence": assessment_object, "draft_report": draft_report},
        indent=2,
        ensure_ascii=False,
    )
    raw = await _chat(CRITIC_SYSTEM_PROMPT, payload, max_tokens=3072)
    return json.loads(_strip_fences(raw))


# ---------------------------------------------------------------------------
# Agent — Fairness / Bias Check
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


async def fairness_check(synthesis_report: Dict[str, Any]) -> Dict[str, Any]:
    """Run Claude as a fairness reviewer on the final synthesis report."""
    payload = json.dumps(synthesis_report, indent=2, ensure_ascii=False)
    raw = await _chat(FAIRNESS_SYSTEM_PROMPT, payload, max_tokens=1024)
    return json.loads(_strip_fences(raw))


# ---------------------------------------------------------------------------
# Streaming variant of the synthesis (for the live results page)
# ---------------------------------------------------------------------------

async def generate_synthesis_stream(assessment_object: Dict[str, Any]) -> AsyncIterator[str]:
    """Stream the draft synthesis report token by token (for SSE)."""
    payload = json.dumps(assessment_object, indent=2, ensure_ascii=False)
    async for delta in _chat_stream(SYNTHESIS_SYSTEM_PROMPT, payload, max_tokens=3072):
        yield delta
