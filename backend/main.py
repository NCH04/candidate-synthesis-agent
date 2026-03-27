"""
AI Candidate Synthesis Agent — FastAPI backend.

FastAPI is the orchestrator: the frontend talks to FastAPI,
and FastAPI calls HrFlow + Claude internally.

Architecture:
  Frontend → FastAPI → HrFlow (CV parse + scoring)
                     → Claude (interview extraction + synthesis)
                     → Fusion logic (local, weighted)
"""

import json as _json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from schemas import InterviewInput
from services.fusion_service import build_fusion_object
from services.hrflow_service import parse_and_score, parse_cv
from services.llm_service import extract_interview_signals, generate_synthesis

app = FastAPI(title="AI Candidate Synthesis Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 14.1 — Parse CV
# ---------------------------------------------------------------------------

@app.post("/api/cv/parse")
async def parse_cv_endpoint(
    file: UploadFile = File(...),
    source_key: str = Form(default=""),
) -> Dict[str, Any]:
    """
    Receive a CV file, forward it to HrFlow, return structured profile data.
    Uses HrFlow POST /v1/profile/parsing/file.
    """
    content = await file.read()
    try:
        result = await parse_cv(
            file_bytes=content,
            filename=file.filename or "resume",
            content_type=file.content_type or "application/octet-stream",
            source_key=source_key,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HrFlow parsing failed: {exc}")

    return {
        "profile_key": result["profile_key"],
        "skills": result["skills"],
        "experience_count": len(result["experiences"]),
        "education_count": len(result["educations"]),
    }


# ---------------------------------------------------------------------------
# 14.2 — Extract Interview Signals
# ---------------------------------------------------------------------------

@app.post("/api/candidate/interview/extract")
async def extract_interview_signals_endpoint(
    payload: InterviewInput,
) -> Dict[str, Any]:
    """
    Send interview feedback text to the interview parsing agent (Claude).
    Returns structured signals.
    """
    try:
        signals = await extract_interview_signals(payload.review_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM extraction failed: {exc}")

    return {
        "interview_type": payload.interview_type,
        "extracted_signals": signals,
    }


# ---------------------------------------------------------------------------
# 14.3 — Build Candidate Assessment
# ---------------------------------------------------------------------------

@app.post("/api/candidate/assessment/build")
async def build_candidate_assessment(payload: dict) -> Dict[str, Any]:
    """
    Combine CV/profile matching, test results, and structured interview signals
    into the Candidate Assessment Object.
    """
    try:
        assessment = build_fusion_object(
            candidate_context=payload["candidate_context"],
            job_context=payload["job_context"],
            cv_matching=payload["cv_profile_matching"],
            raw_test_scores=payload["raw_test_scores"],
            interview_type=payload["interview_type"],
            review_text=payload["review_text"],
            interview_signals=payload["interview_signals"],
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"Missing field: {exc}")

    return assessment


# ---------------------------------------------------------------------------
# 14.4 — Generate Candidate Synthesis
# ---------------------------------------------------------------------------

@app.post("/api/candidate/synthesis/generate")
async def generate_candidate_synthesis(payload: dict) -> Dict[str, Any]:
    """
    Send the fused assessment object to Claude and return the synthesis report.
    """
    try:
        report = await generate_synthesis(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM synthesis failed: {exc}")

    return report


# ---------------------------------------------------------------------------
# 14.5 — Full Pipeline (main demo endpoint)
# ---------------------------------------------------------------------------

@app.post("/api/candidate/full-pipeline")
async def full_pipeline(
    file: UploadFile = File(...),
    candidate_id: str = Form(...),
    candidate_name: str = Form(default=""),
    job_id: str = Form(default=""),          # HrFlow job_key (optional)
    job_title: str = Form(...),
    target_skills: str = Form(default=""),   # comma-separated
    hrflow_board_key: str = Form(default=""), # HrFlow board_key (optional)
    test_results_json: str = Form(...),       # JSON string {"key": score}
    interview_type: str = Form(default="technical_interview"),
    review_text: str = Form(...),
    source_key: str = Form(default=""),
) -> Dict[str, Any]:
    """
    Single demo endpoint — full pipeline:
    1. Parse CV via HrFlow
    2. Score profile/job fit via HrFlow GET /v1/profiles/scoring
    3. Validate & aggregate test results
    4. Extract interview signals via Claude
    5. Build fusion object
    6. Generate final synthesis via Claude
    """
    skills_list = [s.strip() for s in target_skills.split(",") if s.strip()]

    # 1 + 2 — HrFlow: parse + score
    file_bytes = await file.read()
    try:
        cv_result = await parse_and_score(
            file_bytes=file_bytes,
            filename=file.filename or "resume",
            content_type=file.content_type or "application/octet-stream",
            board_key=hrflow_board_key,
            job_key=job_id,
            target_skills=skills_list,
            source_key=source_key,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HrFlow error: {exc}")

    # 3 — Validate test results
    try:
        raw_scores: Dict[str, int] = _json.loads(test_results_json)
        if not isinstance(raw_scores, dict):
            raise ValueError("test_results_json must be a JSON object")
        for k, v in raw_scores.items():
            if not (1 <= int(v) <= 5):
                raise ValueError(f"Score for '{k}' must be between 1 and 5")
        raw_scores = {k: int(v) for k, v in raw_scores.items()}
    except (ValueError, _json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid test_results_json: {exc}")

    # 4 — Claude: extract interview signals
    try:
        interview_signals = await extract_interview_signals(review_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Interview extraction failed: {exc}")

    # 5 — Fusion
    candidate_context = {"candidate_id": candidate_id, "candidate_name": candidate_name}
    job_context = {"job_id": job_id, "job_title": job_title, "target_skills": skills_list}

    assessment = build_fusion_object(
        candidate_context=candidate_context,
        job_context=job_context,
        cv_matching=cv_result,
        raw_test_scores=raw_scores,
        interview_type=interview_type,
        review_text=review_text,
        interview_signals=interview_signals,
    )

    # 6 — Claude: final synthesis
    try:
        report = await generate_synthesis(assessment)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Synthesis generation failed: {exc}")

    return {
        "pipeline_steps": {
            "cv_parsed": True,
            "profile_scored": True,
            "interview_extracted": True,
            "fusion_completed": True,
            "synthesis_generated": True,
        },
        "assessment": assessment,
        "synthesis_report": report,
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}
