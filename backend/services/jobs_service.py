"""
Jobs service — loads jobs from local JSON file.

No HrFlow API call needed. The jobs_fallback.json at the backend root
is the source of truth for autocomplete and skill hints.
"""

import json
import os
from typing import Any, Dict, List, Optional

_JOBS_FILE = os.path.join(os.path.dirname(__file__), "..", "jobs_fallback.json")

_jobs_cache: List[Dict[str, Any]] = []


def load_jobs_from_file() -> None:
    """Load jobs from local JSON file into memory."""
    global _jobs_cache
    try:
        with open(_JOBS_FILE, "r", encoding="utf-8") as f:
            _jobs_cache = json.load(f)
        print(f"[jobs_service] Loaded {len(_jobs_cache)} jobs from local file.")
    except Exception as exc:
        print(f"[jobs_service] Could not load jobs_fallback.json: {exc}")
        _jobs_cache = []


def get_jobs() -> List[Dict[str, Any]]:
    return _jobs_cache


def get_job_by_key(job_key: str) -> Optional[Dict[str, Any]]:
    for job in _jobs_cache:
        if job["key"] == job_key:
            return job
    return None
