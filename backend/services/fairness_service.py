"""
Cheap deterministic fairness pre-filter.

A full LLM fairness review is valuable but costs a Claude call on every
evaluation. In practice the synthesis prompt already forbids non-job-relevant
content, so the vast majority of reports are clean and the LLM reviewer just
returns "ok".

This pre-filter scans the report text locally for terms that *could* indicate a
protected-attribute reference or prestige bias. Only when it finds a candidate
term do we escalate to the LLM reviewer (which then decides if it's a real
issue). When nothing matches we return "ok" immediately — no API call.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# Word-boundary terms that may signal a protected attribute or biased framing.
# This is intentionally broad: false positives just trigger an LLM check, they
# don't produce a flag on their own.
_SENSITIVE_TERMS = [
    # Age
    "age", "aged", "young", "younger", "old", "older", "elderly", "junior age",
    "years old", "born in", "generation", "millennial", "boomer",
    # Gender / family
    "male", "female", "man", "woman", "men", "women", "he ", "she ",
    "his ", "her ", "pregnant", "maternity", "paternity", "married",
    "single mother", "single father", "husband", "wife", "children", "kids",
    # Origin / ethnicity / nationality / religion
    "ethnic", "ethnicity", "race", "racial", "nationality", "foreign",
    "immigrant", "religion", "religious", "muslim", "christian", "jewish",
    "accent", "native speaker",
    # Health / disability
    "disability", "disabled", "handicap", "illness", "mental health",
    "depression", "anxiety",
    # Prestige proxies (school/company name used as a proxy for skill)
    "prestigious", "elite school", "top university", "ivy league", "grande école",
]

_SENSITIVE_RE = re.compile(
    r"(?<![a-z])(" + "|".join(re.escape(t.strip()) for t in _SENSITIVE_TERMS) + r")",
    re.IGNORECASE,
)


def _collect_text(report: Dict[str, Any]) -> str:
    """Flatten the human-readable fields of a synthesis report into one string."""
    parts: List[str] = []

    for key in (
        "executive_summary",
        "technical_assessment",
        "behavioral_assessment",
        "consistency_analysis",
        "justification",
        "domain_fit",
    ):
        val = report.get(key)
        if isinstance(val, str):
            parts.append(val)

    for key in ("strengths", "weaknesses", "risks"):
        for item in report.get(key, []) or []:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))

    return "\n".join(parts)


def needs_llm_fairness_review(report: Dict[str, Any]) -> bool:
    """True if the report contains any sensitive term and should be LLM-reviewed."""
    text = _collect_text(report)
    return bool(_SENSITIVE_RE.search(text))


def clean_fairness_result() -> Dict[str, Any]:
    """The default 'all clear' result, returned without any API call."""
    return {"status": "ok", "flags": []}
