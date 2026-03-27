"""
HrFlow API service.

Two calls are made:
1. POST /v1/profile/parsing/file  — parse the uploaded CV
2. GET  /v1/profiles/scoring      — score the parsed profile against a job
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

import httpx

HRFLOW_API_KEY = os.getenv("HRFLOW_API_KEY", "ask_d2055968eae428d9444f5de212e9d516")
HRFLOW_USER_EMAIL = os.getenv("HRFLOW_USER_EMAIL", "recruiter@example.com")
HRFLOW_SOURCE_KEY = os.getenv("HRFLOW_SOURCE_KEY", "da13ffd3b3fe72839848d91144b4e39d5cba2819")

BASE_URL = "https://api.hrflow.ai/v1"

_HEADERS = {
    "X-API-KEY": HRFLOW_API_KEY,
    "X-USER-EMAIL": HRFLOW_USER_EMAIL,
}


# ---------------------------------------------------------------------------
# CV Parsing
# ---------------------------------------------------------------------------

async def parse_cv(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    source_key: str = "",
) -> Dict[str, Any]:
    """
    Upload a CV to HrFlow and return the parsed profile data.

    Returns a dict with keys: profile_key, skills, experiences, educations, summary
    """
    source = source_key or HRFLOW_SOURCE_KEY
    if not source:
        raise ValueError("HRFLOW_SOURCE_KEY is not configured")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/profile/parsing/file",
            headers=_HEADERS,
            data={"source_key": source},
            files={"file": (filename, file_bytes, content_type)},
        )

    response.raise_for_status()
    body = response.json()

    parsing = body.get("data", {}).get("parsing", {})
    profile_key = body.get("data", {}).get("profile", {}).get("key", "")

    # Flatten skill names
    skills: List[str] = [
        s.get("name", "") for s in parsing.get("skills", []) if s.get("name")
    ]

    return {
        "profile_key": profile_key,
        "skills": skills,
        "experiences": parsing.get("experiences", []),
        "educations": parsing.get("educations", []),
        "raw_parsing": parsing,
    }


# ---------------------------------------------------------------------------
# Profile / Job Scoring
# ---------------------------------------------------------------------------

async def score_profile(
    profile_key: str,
    source_key: str,
    board_key: str,
    job_key: str,
    max_retries: int = 3,
    retry_delay: float = 3.0,
) -> float:
    """
    Call GET /v1/profiles/scoring to retrieve the matching score for a profile.

    HrFlow indexes profiles asynchronously after parsing, so we retry a few
    times if the profile is not yet present in the scoring results.

    Returns a normalized score in [0, 100].
    """
    source = source_key or HRFLOW_SOURCE_KEY
    if not source:
        raise ValueError("HRFLOW_SOURCE_KEY is not configured")

    params = {
        "source_key": source,
        "board_key": board_key,
        "job_key": job_key,
        "sort_by": "scoring",
        "limit": 30,
    }

    for attempt in range(max_retries):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{BASE_URL}/profiles/scoring",
                headers=_HEADERS,
                params=params,
            )

        if response.status_code == 200:
            body = response.json()
            profiles = body.get("data", {}).get("profiles", [])
            predictions = body.get("data", {}).get("predictions", [])

            for idx, profile in enumerate(profiles):
                if profile.get("key") == profile_key:
                    # predictions is a list of [1-P, P]; P is the match score
                    if idx < len(predictions):
                        p = predictions[idx]
                        raw_score = p[1] if isinstance(p, list) else p
                        return round(float(raw_score) * 100, 1)

        # Profile not indexed yet — wait and retry
        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)

    # Fallback: no score found after retries
    return 0.0


# ---------------------------------------------------------------------------
# Combined helper used by the full pipeline
# ---------------------------------------------------------------------------

async def parse_and_score(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    board_key: str,
    job_key: str,
    target_skills: List[str],
    source_key: str = "",
) -> Dict[str, Any]:
    """
    Parse a CV then score it against a job.

    Returns CVProfileMatching-compatible dict.
    """
    parsed = await parse_cv(file_bytes, filename, content_type, source_key)
    profile_key = parsed["profile_key"]
    candidate_skills = [s.lower() for s in parsed["skills"]]
    target_skills_lower = [s.lower() for s in target_skills]

    # Skill matching (local, fast — does not depend on HrFlow indexing)
    matched = [s for s in target_skills if s.lower() in candidate_skills]
    missing = [s for s in target_skills if s.lower() not in candidate_skills]

    # HrFlow scoring
    hrflow_score = 0.0
    if profile_key and board_key and job_key:
        hrflow_score = await score_profile(profile_key, source_key, board_key, job_key)

    # Fallback score based on skill overlap when HrFlow score is unavailable
    if hrflow_score == 0.0 and target_skills:
        hrflow_score = round(len(matched) / len(target_skills) * 100, 1)

    # Experience fit heuristic from number of experience entries
    exp_count = len(parsed.get("experiences", []))
    if exp_count >= 3:
        experience_fit = "strong"
    elif exp_count == 2:
        experience_fit = "good"
    elif exp_count == 1:
        experience_fit = "fair"
    else:
        experience_fit = "poor"

    match_pct = len(matched) / len(target_skills) * 100 if target_skills else 0
    summary = (
        f"Candidate matches {len(matched)}/{len(target_skills)} target skills "
        f"({match_pct:.0f}%). "
        f"HrFlow relevance score: {hrflow_score:.0f}/100. "
        f"Experience fit: {experience_fit}."
    )

    return {
        "profile_key": profile_key,
        "score": hrflow_score,
        "matched_skills": matched,
        "missing_skills": missing,
        "experience_fit": experience_fit,
        "summary": summary,
    }
