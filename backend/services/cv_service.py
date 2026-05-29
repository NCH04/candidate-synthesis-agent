"""
CV service — PDF text extraction + Claude-based profile parsing and scoring.

Pipeline:
  1. extract_text_from_pdf(file_bytes)        → raw text
  2. llm_service.parse_cv_structure(text)     → {skills, experiences, education, ...}
  3. llm_service.extract_candidate_name(text) → reliable full name
  4. skill_match_service.match_skills(...)    → semantic matched / missing
  5. llm_service.score_profile_job(...)       → fit score + summary

This replaces the previous external CV parsing dependency.
Everything runs against Claude + a local embedding model — no third-party
recruitment API required.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

import pdfplumber

from .llm_service import (
    extract_candidate_name,
    parse_cv_structure,
    score_profile_job,
)
from .skill_match_service import match_skills


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF (uses pdfplumber)."""
    text_parts: List[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts).strip()


async def parse_cv(file_bytes: bytes, filename: str, content_type: str) -> Dict[str, Any]:
    """
    Parse a CV file end-to-end:
      - extract raw text (PDF or text/plain),
      - have Claude extract a structured profile,
      - have Claude re-extract the candidate name (more reliable than parsers),
      - return a dict ready to feed into scoring + final synthesis.

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
    name_lower = filename.lower()
    if name_lower.endswith(".pdf") or content_type == "application/pdf":
        raw_text = extract_text_from_pdf(file_bytes)
    else:
        # Plain text or markdown CV
        raw_text = file_bytes.decode("utf-8", errors="replace")

    if not raw_text.strip():
        raise ValueError("Could not extract any text from the uploaded CV.")

    profile = await parse_cv_structure(raw_text)

    # Prefer LLM-extracted full name (Claude is good at this and ignores headers/footers)
    try:
        extracted_name = (await extract_candidate_name(raw_text)).strip()
        if extracted_name:
            profile["full_name"] = extracted_name
    except Exception:
        pass

    profile["raw_text"] = raw_text
    return profile


async def score_profile_against_job(
    profile: Dict[str, Any],
    job: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Combine semantic skill matching (local embeddings) with Claude-based scoring.

    Returns:
      {
        "score": 0-100,
        "matched_skills": [...],
        "missing_skills": [...],
        "experience_fit": "...",
        "summary": "..."
      }
    """
    candidate_skills: List[str] = profile.get("skills") or []
    target_skills: List[str] = job.get("skills") or job.get("target_skills") or []

    # 1) Semantic skill match (no API call — local model)
    skill_match = match_skills(candidate_skills, target_skills)

    # 2) Claude-based qualitative score (sees full profile + job description)
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
    job: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    End-to-end: parse CV + (optionally) score against a job.

    Returned shape matches what the orchestrator (main.py) expects for the
    cv_profile_matching block of the assessment object.
    """
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
