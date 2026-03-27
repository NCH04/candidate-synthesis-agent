"""
LLM service using the Anthropic Claude API.

Two agents:
  - Agent 1: Interview Parsing Agent
  - Agent 2: Final Synthesis Agent
"""

import json
import os
from typing import Any, Dict

import anthropic

_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
MODEL = "claude-sonnet-4-6"


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
    """Call Claude to extract structured signals from raw interview text."""
    message = await _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=INTERVIEW_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": review_text}],
    )
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


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
  "justification": "..."
}
"""


async def generate_synthesis(assessment_object: Dict[str, Any]) -> Dict[str, Any]:
    """Call Claude to generate the final candidate synthesis report."""
    payload = json.dumps(assessment_object, indent=2, ensure_ascii=False)
    message = await _client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYNTHESIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": payload}],
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
