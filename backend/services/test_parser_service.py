"""
Deterministic test-sheet parser.

Most evaluation forms follow a regular layout:

    1. Python — backend development
       Score: 4 / 5
       Notes: ...

When that structure is present we extract the scores with a regex — for free,
deterministically, with zero hallucination — instead of paying for a Claude
call. The orchestrator falls back to the LLM parser only when the regex parser
can't find enough scored competencies.

Title parsing note
------------------
An earlier version cut the competency title at the first `-`, so
"Problem-solving under pressure" became "Problem" and no longer matched the
"problem-solving" soft-skill keyword — it was filed as a technical competency
and skewed the weighted score. Titles are now cut only on real separators
(colon, em/en dash, or a *spaced* hyphen), never inside a hyphenated word.
"""

from __future__ import annotations

import re
from typing import Any

# "Score: 4 / 5", "Score : 4/5", "Rating: 3 of 5", "Note : 4 sur 5"
_SCORE_RE = re.compile(
    r"(?:score|rating|note|notation)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(?:/|of|sur)\s*(\d+)",
    re.IGNORECASE,
)

# A competency title line: an optional "1." / "-" / "*" marker, then the title.
# The whole remainder of the line is captured; `_clean_title` cuts it.
_TITLE_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•])?\s*([A-Za-z][^\n]{0,79})$")

# Real separators between a competency name and its description.
# A hyphen only separates when surrounded by whitespace ("Python - backend"),
# never inside a word ("Problem-solving").
_TITLE_SEPARATOR_RE = re.compile(r"\s*[:—–]\s*|\s+-\s+")

_NON_COMPETENCY_TITLES = {
    "score", "rating", "note", "notes", "candidate", "evaluator", "interviewer",
    "position", "date", "section", "technical skills", "soft skills",
    "motivation", "overall", "summary", "comments", "total", "result", "results",
    "evaluation", "assessment", "recommendation",
}

# Keyword → bucket. Matched as substrings against the lower-cased title, so
# "problem-solving" matches "Problem-solving under pressure".
_SOFT_KEYWORDS = {
    "communication", "teamwork", "collaboration", "leadership", "adaptability",
    "creativity", "autonomy", "rigor", "rigour", "organization", "organisation",
    "empathy", "listening", "conflict", "presentation", "interpersonal",
    "problem solving", "problem-solving", "critical thinking", "time management",
    "learning agility", "curiosity", "mentoring", "stress management",
    "attention to detail", "pragmatism", "ownership",
}
_MOTIVATION_KEYWORDS = {
    "motivation", "role interest", "role_interest", "interest", "engagement",
    "commitment", "drive", "ambition", "culture fit", "culture_fit",
    "career goal", "career goals", "goals alignment", "aspiration",
    "long-term", "long term", "enthusiasm", "company fit",
}


def _bucket(skill: str) -> str:
    """Classify a competency title into technical / soft / motivation."""
    low = skill.lower().strip()
    if any(k in low for k in _MOTIVATION_KEYWORDS):
        return "motivation"
    if any(k in low for k in _SOFT_KEYWORDS):
        return "soft"
    return "technical"


def _clean_title(raw: str) -> str:
    """Cut a title line at its first real separator and strip punctuation."""
    cut = _TITLE_SEPARATOR_RE.split(raw, maxsplit=1)[0]
    return cut.strip(" .:-—–\t")


def _normalize_skill_key(skill: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", skill.lower().strip()).strip("_")


def _scale_to_5(value: float, out_of: int) -> int:
    """Rescale a score to the 1-5 integer scale the assessment schema requires."""
    if out_of <= 0:
        return 0
    scaled = round(value / out_of * 5)
    return max(1, min(5, scaled))


def parse_test_sheet_regex(text: str) -> dict[str, Any] | None:
    """Try to parse a test sheet deterministically.

    Returns {scores, target_skills} on success, or None if the layout doesn't
    expose at least three scored competencies (caller falls back to the LLM).
    """
    pairs: list[tuple[str, int]] = []
    pending_title: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        score_match = _SCORE_RE.search(line)
        if score_match:
            value = float(score_match.group(1).replace(",", "."))
            out_of = int(score_match.group(2))
            # The competency name is either inline before "Score:" or the most
            # recent title line we saw.
            inline = _clean_title(line[: score_match.start()])
            title = inline or pending_title
            if title:
                pairs.append((title, _scale_to_5(value, out_of)))
            pending_title = None
            continue

        title_match = _TITLE_RE.match(line)
        if title_match:
            candidate = _clean_title(title_match.group(1))
            if candidate and candidate.lower() not in _NON_COMPETENCY_TITLES:
                pending_title = candidate

    if len(pairs) < 3:
        return None

    scores: dict[str, int] = {}
    target_skills: list[str] = []
    for skill, score in pairs:
        key = f"{_bucket(skill)}.{_normalize_skill_key(skill)}"
        if key in scores:
            continue
        scores[key] = score
        target_skills.append(skill.strip())

    return {"scores": scores, "target_skills": target_skills}
