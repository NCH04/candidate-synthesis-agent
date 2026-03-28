"""
Jobs cache service.

Fetches all jobs from the HrFlow board once at startup and keeps them
in memory. The frontend uses /api/jobs/list for autocomplete without
ever seeing job keys directly.
"""

import os
from typing import Any, Dict, List

import httpx

HRFLOW_API_KEY    = os.getenv("HRFLOW_API_KEY", "")
HRFLOW_USER_EMAIL = os.getenv("HRFLOW_USER_EMAIL", "")
HRFLOW_BOARD_KEY  = os.getenv("HRFLOW_BOARD_KEY", "dbe92e653fa4f9c89ff335c29e91f49a1f7d448f")

BASE_URL = "https://api.hrflow.ai/v1"

_HEADERS = {
    "X-API-KEY": HRFLOW_API_KEY,
    "X-USER-EMAIL": HRFLOW_USER_EMAIL,
}

# In-memory cache — populated once at startup
_jobs_cache: List[Dict[str, Any]] = []


async def load_jobs() -> None:
    """Fetch all jobs from the HrFlow board and store in _jobs_cache."""
    global _jobs_cache

    jobs: List[Dict[str, Any]] = []
    page = 1

    while True:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{BASE_URL}/jobs/searching",
                headers=_HEADERS,
                params={
                    "board_keys": f'["{HRFLOW_BOARD_KEY}"]',
                    "limit": 30,
                    "page": page,
                },
            )

        if resp.status_code != 200:
            print(f"[jobs_service] HrFlow returned {resp.status_code}: {resp.text[:200]}")
            break

        body = resp.json()
        page_jobs = body.get("data", {}).get("jobs", [])

        if not page_jobs:
            break

        for job in page_jobs:
            skills = [
                s.get("name", "")
                for s in job.get("skills", [])
                if s.get("name")
            ]
            jobs.append({
                "key":     job.get("key", ""),
                "title":   job.get("name", ""),
                "skills":  skills,
                "summary": job.get("summary", "") or "",
            })

        # Stop if we got everything
        total = body.get("data", {}).get("meta", {}).get("total", 0)
        if len(jobs) >= total or total == 0:
            break
        page += 1

    _jobs_cache = jobs
    print(f"[jobs_service] Loaded {len(_jobs_cache)} jobs from HrFlow board.")


def get_jobs() -> List[Dict[str, Any]]:
    """Return the cached jobs list (key is included for backend use only)."""
    return _jobs_cache


def get_job_by_key(job_key: str) -> Dict[str, Any] | None:
    """Find a job in cache by its HrFlow key."""
    for job in _jobs_cache:
        if job["key"] == job_key:
            return job
    return None
