"""
Deterministic test-sheet parser.

Most evaluation forms follow a regular layout:

    1. Python — backend development
       Score: 4 / 5
       Notes: ...

When that structure is present we can extract the scores with a regex — for
free, deterministically, with zero hallucination — instead of paying for a
Claude call. The orchestrator falls back to the LLM parser only when the regex
parser can't find enough scored competencies.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# "Score: 4 / 5", "Score : 4/5", "Rating: 3 of 5", "4/5"
_SCORE_RE = re.compile(
    r"(?:score|rating|note)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:/|of|sur)\s*(\d+)",
    re.IGNORECASE,
)
# A competency title line, e.g. "1. Python — backend development" or
# "- Communication: collaboration"
_TITLE_RE = re.compile(
    r"^\s*(?:\d+\.|[-*•])?\s*([A-Za-z][\w &/+().'-]{1,60}?)\s*(?:[—:\-]|$)"
)

# Keyword → bucket prefix for grouping
_SOFT_KEYWORDS = {
    "communication", "teamwork", "collaboration", "leadership", "adaptability",
    "creativity", "autonomy", "rigor", "rigour", "organization", "organisation",
    "empathy", "listening", "conflict", "presentation", "interpersonal",
    "problem solving", "problem-solving", "critical thinking", "time management",
}
_MOTIVATION_KEYWORDS = {
    "motivation", "role interest", "role_interest", "interest", "engagement",
    "commitment", "drive", "ambition", "culture fit", "culture_fit",
}


def _bucket(skill: str) -> str:
    low = skill.lower().strip()
    if any(k in low for k in _MOTIVATION_KEYWORDS):
        return "motivation"
    if any(k in low for k in _SOFT_KEYWORDS):
        return "soft"
    return "technical"


def _normalize_skill_key(skill: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", skill.lower().strip()).strip("_")


def _scale_to_5(value: float, out_of: int) -> int:
    if out_of <= 0:
        return 0
    scaled = round(value / out_of * 5)
    return max(1, min(5, scaled))


def parse_test_sheet_regex(text: str) -> Optional[Dict[str, Any]]:
    """Try to parse a test sheet deterministically.

    Returns a dict {scores, target_skills} on success, or None if the layout
    doesn't expose enough scored competencies (caller should fall back to LLM).
    """
    lines = text.splitlines()
    pairs: List[Tuple[str, int]] = []
    pending_title: Optional[str] = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        score_match = _SCORE_RE.search(line)
        if score_match:
            value = float(score_match.group(1))
            out_of = int(score_match.group(2))
            # The competency name is either on this line before "Score:" or the
            # most recent title line we saw.
            inline = line[: score_match.start()].strip(" .:-—")
            title = inline or pending_title
            if title:
                pairs.append((title, _scale_to_5(value, out_of)))
            pending_title = None
            continue

        # Not a score line — treat as a potential title for the next score line
        title_match = _TITLE_RE.match(line)
        if title_match:
            candidate = title_match.group(1).strip()
            # Ignore obvious non-competency lines
            if candidate.lower() not in {
                "score", "rating", "note", "notes", "candidate", "evaluator",
                "position", "date", "section", "technical skills", "soft skills",
            }:
                pending_title = candidate

    # Need a meaningful number of competencies to trust the regex parser
    if len(pairs) < 3:
        return None

    scores: Dict[str, int] = {}
    target_skills: List[str] = []
    for skill, score in pairs:
        bucket = _bucket(skill)
        key = f"{bucket}.{_normalize_skill_key(skill)}"
        if key in scores:
            continue
        scores[key] = score
        target_skills.append(skill.strip().title())

    return {"scores": scores, "target_skills": target_skills}
