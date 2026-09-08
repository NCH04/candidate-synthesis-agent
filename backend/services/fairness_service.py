"""
Cheap deterministic fairness pre-filter.

A full LLM fairness review is valuable but costs a Claude call on every
evaluation. In practice the synthesis prompt already forbids non-job-relevant
content, so the majority of reports are clean and the LLM reviewer just
returns "ok".

This pre-filter scans the report text locally for terms that *could* indicate a
protected-attribute reference or prestige bias. Only when it finds a candidate
term do we escalate to the LLM reviewer (which then decides if it's a real
issue). When nothing matches we return "ok" immediately — no API call.

IMPORTANT — word boundaries.
The terms below are matched with `\\b...\\b` on BOTH sides. An earlier version
only anchored the left side, so "man" matched *man*agement, "he" matched
*he*lp/*he*ld, and "men" matched *men*toring — meaning virtually every report
escalated to the LLM and the cost saving never materialised. Any new term must
keep both boundaries.
"""

from __future__ import annotations

import re
from typing import Any

# Terms that may signal a protected attribute or biased framing.
# Intentionally broad: a false positive only triggers an LLM check, it does not
# produce a flag on its own.
_SENSITIVE_TERMS = [
    # Age
    "age", "aged", "young", "younger", "old", "older", "elderly",
    "years old", "born in", "generation", "millennial", "boomer",
    # Gender / family
    "male", "female", "man", "woman", "men", "women",
    "he", "she", "his", "her", "hers",
    "pregnant", "maternity", "paternity", "married",
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
    r"\b(" + "|".join(re.escape(t.strip()) for t in _SENSITIVE_TERMS) + r")\b",
    re.IGNORECASE,
)

_TEXT_FIELDS = (
    "executive_summary",
    "technical_assessment",
    "behavioral_assessment",
    "consistency_analysis",
    "justification",
    "domain_fit",
)
_CITED_FIELDS = ("strengths", "weaknesses", "risks")


def _collect_text(report: dict[str, Any]) -> str:
    """Flatten the human-readable fields of a synthesis report into one string."""
    parts: list[str] = []

    for key in _TEXT_FIELDS:
        val = report.get(key)
        if isinstance(val, str):
            parts.append(val)

    for key in _CITED_FIELDS:
        for item in report.get(key, []) or []:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))

    return "\n".join(parts)


def sensitive_terms_found(report: dict[str, Any]) -> list[str]:
    """The distinct sensitive terms present in the report (lower-cased).

    Exposed for observability: it makes it possible to see *why* a report was
    escalated to the LLM reviewer instead of guessing.
    """
    found = {m.group(0).lower() for m in _SENSITIVE_RE.finditer(_collect_text(report))}
    return sorted(found)


def needs_llm_fairness_review(report: dict[str, Any]) -> bool:
    """True if the report contains any sensitive term and should be LLM-reviewed."""
    return bool(_SENSITIVE_RE.search(_collect_text(report)))


def clean_fairness_result() -> dict[str, Any]:
    """The default 'all clear' result, returned without any API call."""
    return {"status": "ok", "flags": []}
