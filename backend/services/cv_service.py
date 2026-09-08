"""
CV service — PDF text extraction + Claude-based profile parsing and scoring.

Pipeline:
  1. extract_text_from_pdf(file_bytes)        → raw text
  2. llm_service.parse_cv_structure(text)     → {full_name, skills, experiences, education, ...}
  3. skill_match_service.match_skills(...)    → semantic matched / missing
  4. llm_service.score_profile_job(...)       → fit score + summary

Cost controls:
  * The structured parse already returns full_name, so there is no separate
    name-extraction call (that round-trip was redundant).
  * Parsed profiles are cached by a hash of the file bytes — re-uploading the
    same CV skips the parse entirely.
"""

from __future__ import annotations

import hashlib
import io
from collections import OrderedDict
from typing import Any

import pdfplumber

from .llm_service import parse_cv_structure, score_profile_job
from .skill_match_service import match_skills

# ---------------------------------------------------------------------------
# Tiny in-memory LRU cache (process-local). Keyed by sha256 of the file bytes.
# ---------------------------------------------------------------------------

_CACHE_MAX = 64
_profile_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()


def _cache_get(key: str) -> dict[str, Any] | None:
    if key in _profile_cache:
        _profile_cache.move_to_end(key)
        return _profile_cache[key]
    return None


def _cache_put(key: str, value: dict[str, Any]) -> None:
    _profile_cache[key] = value
    _profile_cache.move_to_end(key)
    while len(_profile_cache) > _CACHE_MAX:
        _profile_cache.popitem(last=False)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF (uses pdfplumber)."""
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts).strip()


async def parse_cv(file_bytes: bytes, filename: str, content_type: str) -> dict[str, Any]:
    """
    Parse a CV file end-to-end:
      - extract raw text (PDF or text/plain),
      - have Claude extract a structured profile (incl. full_name),
      - cache the result by file hash.

    Returned dict shape:
      {
        "raw_text": "...",
        "full_name": "Jane Smith",
        "skills": ["Python", ...],
        "experiences": [...],
        "education": [...],
        "summary": "..."
      }
    """
    cache_key = _hash_bytes(file_bytes)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    name_lower = filename.lower()
    if name_lower.endswith(".pdf") or content_type == "application/pdf":
        raw_text = extract_text_from_pdf(file_bytes)
    else:
        raw_text = file_bytes.decode("utf-8", errors="replace")

    if not raw_text.strip():
        raise ValueError("Could not extract any text from the uploaded CV.")

    profile = await parse_cv_structure(raw_text)
    profile["raw_text"] = raw_text

    _cache_put(cache_key, profile)
    return profile


async def score_profile_against_job(
    profile: dict[str, Any],
    job: dict[str, Any],
) -> dict[str, Any]:
    """
    Combine semantic skill matching (local embeddings) with Claude-based scoring.

    Returns:
      { "score", "matched_skills", "missing_skills", "experience_fit", "summary" }
    """
    candidate_skills: list[str] = profile.get("skills") or []
    target_skills: list[str] = job.get("skills") or job.get("target_skills") or []

    # 1) Semantic skill match (no API call — local model)
    skill_match = match_skills(candidate_skills, target_skills)

    # 2) Claude-based qualitative score (smart tier)
    claude_eval = await score_profile_job(
        profile={
            "skills": candidate_skills,
            "experiences": profile.get("experiences", []),
            "education": profile.get("education", []),
            "summary": profile.get("summary", ""),
        },
        job={
            "title": job.get("title", ""),
            "skills": target_skills,
            "summary": job.get("summary", ""),
        },
    )

    return {
        "score": float(claude_eval.get("score", 0)),
        "matched_skills": skill_match["matched"],
        "missing_skills": skill_match["missing"],
        "experience_fit": claude_eval.get("experience_fit", ""),
        "summary": claude_eval.get("summary", ""),
    }


async def parse_and_score(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    job: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """End-to-end: parse CV + (optionally) score against a job."""
    profile = await parse_cv(file_bytes, filename, content_type)

    if job:
        scoring = await score_profile_against_job(profile, job)
    else:
        scoring = {
            "score": 0.0,
            "matched_skills": [],
            "missing_skills": [],
            "experience_fit": "",
            "summary": "No job context provided.",
        }

    return {"profile": profile, "scoring": scoring}
