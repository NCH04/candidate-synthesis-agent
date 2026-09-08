"""
Demo mode — serve pre-computed sample results with zero API calls.

When DEMO_MODE=true the whole pipeline returns a canned candidate evaluation
loaded from demo_data/sample.json. This lets a public deployment (e.g. a
Hugging Face Space) be tried by anyone without an Anthropic key and without
spending any API budget. Real evaluations require DEMO_MODE=false + a key.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

_SAMPLE_PATH = Path(__file__).resolve().parent.parent / "demo_data" / "sample.json"

_sample: dict[str, Any] | None = None


def is_demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


def _load() -> dict[str, Any]:
    global _sample
    if _sample is None:
        with open(_SAMPLE_PATH, encoding="utf-8") as f:
            _sample = json.load(f)
    return _sample


def demo_cv_parse() -> dict[str, Any]:
    return dict(_load()["cv_parse"])


def demo_test_parse() -> dict[str, Any]:
    return dict(_load()["test_parse"])


def demo_assessment() -> dict[str, Any]:
    return dict(_load()["assessment"])


def demo_synthesis_report() -> dict[str, Any]:
    return dict(_load()["synthesis_report"])


def demo_pipeline_result() -> dict[str, Any]:
    data = _load()
    return {
        "pipeline_steps": {
            "cv_parsed": True,
            "profile_scored": True,
            "interview_extracted": True,
            "fusion_completed": True,
            "synthesis_generated": True,
            "critic_refined": True,
            "fairness_checked": True,
        },
        "assessment": data["assessment"],
        "synthesis_report": data["synthesis_report"],
    }


async def fake_synthesis_stream() -> AsyncIterator[str]:
    """Emit the canned synthesis JSON in small chunks to mimic live streaming."""
    text = json.dumps(demo_synthesis_report(), indent=2, ensure_ascii=False)
    chunk = 24
    for i in range(0, len(text), chunk):
        yield text[i : i + chunk]
        await asyncio.sleep(0.02)
