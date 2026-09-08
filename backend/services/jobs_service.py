"""
Jobs service — loads job openings from a local JSON file.

The jobs.json catalogue is the source of truth for autocomplete and
target-skill hints in the UI.
"""

import json
import os
from typing import Any

_JOBS_FILE = os.path.join(os.path.dirname(__file__), "..", "jobs.json")

_jobs_cache: list[dict[str, Any]] = []


def load_jobs_from_file() -> None:
    """Load jobs from local JSON file into memory."""
    global _jobs_cache
    try:
        with open(_JOBS_FILE, encoding="utf-8") as f:
            _jobs_cache = json.load(f)
        print(f"[jobs_service] Loaded {len(_jobs_cache)} jobs from local file.")
    except Exception as exc:
        print(f"[jobs_service] Could not load jobs.json: {exc}")
        _jobs_cache = []


def get_jobs() -> list[dict[str, Any]]:
    return _jobs_cache


def get_job_by_key(job_key: str) -> dict[str, Any] | None:
    for job in _jobs_cache:
        if job["key"] == job_key:
            return job
    return None
