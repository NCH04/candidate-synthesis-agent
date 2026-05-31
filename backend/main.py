"""
AI Candidate Synthesis Agent — FastAPI backend.

FastAPI is the orchestrator. The frontend talks to FastAPI and FastAPI runs
the full multi-agent Claude pipeline:

  Frontend → FastAPI → Claude (CV parse + profile/job scoring)
                     → Claude (interview signal extraction)
                     → Claude (test sheet parsing)
                     → Fusion logic (local, weighted)
                     → Claude (draft synthesis with citations)
                     → Claude (critic / refiner)
                     → Claude (fairness reviewer)
"""

from __future__ import annotations

import json as _json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

try:
    from .schemas import InterviewInput
    from .services import demo_service
    from .services.cv_service import extract_text_from_pdf, parse_and_score, parse_cv
    from .services.fairness_service import clean_fairness_result, needs_llm_fairness_review
    from .services.fusion_service import build_fusion_object
    from .services.jobs_service import get_job_by_key, get_jobs, load_jobs_from_file
    from .services.test_parser_service import parse_test_sheet_regex
    from .services.llm_service import (
        FAST_MODEL,
        SMART_MODEL,
        critique_and_refine_synthesis,
        extract_interview_signals,
        fairness_check,
        generate_synthesis,
        generate_synthesis_stream,
        parse_test_sheet,
    )
except ImportError:
    from schemas import InterviewInput  # type: ignore
    from services import demo_service  # type: ignore
    from services.cv_service import extract_text_from_pdf, parse_and_score, parse_cv  # type: ignore
    from services.fairness_service import clean_fairness_result, needs_llm_fairness_review  # type: ignore
    from services.fusion_service import build_fusion_object  # type: ignore
    from services.jobs_service import get_job_by_key, get_jobs, load_jobs_from_file  # type: ignore
    from services.test_parser_service import parse_test_sheet_regex  # type: ignore
    from services.llm_service import (  # type: ignore
        FAST_MODEL,
        SMART_MODEL,
        critique_and_refine_synthesis,
        extract_interview_signals,
        fairness_check,
        generate_synthesis,
        generate_synthesis_stream,
        parse_test_sheet,
    )


def _economy_mode() -> bool:
    """When true, skip the critic + fairness passes (the two priciest steps)."""
    return os.getenv("ECONOMY_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load jobs from local JSON file on startup."""
    load_jobs_from_file()
    yield


app = FastAPI(title="AI Candidate Synthesis Agent", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Runtime config (so the frontend can show a demo banner, etc.)
# ---------------------------------------------------------------------------

@app.get("/api/config")
async def get_config() -> Dict[str, Any]:
    return {
        "demo_mode": demo_service.is_demo_mode(),
        "economy_mode": _economy_mode(),
        "models": {"fast": FAST_MODEL, "smart": SMART_MODEL},
    }


# ---------------------------------------------------------------------------
# CV — parse only (used at upload time to auto-fill candidate name/skills)
# ---------------------------------------------------------------------------

@app.post("/api/cv/parse")
async def parse_cv_endpoint(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Parse a CV file via Claude and return a structured profile."""
    if demo_service.is_demo_mode():
        return demo_service.demo_cv_parse()

    content = await file.read()
    try:
        profile = await parse_cv(
            file_bytes=content,
            filename=file.filename or "resume",
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CV parsing failed: {exc}")

    return {
        "full_name": profile.get("full_name", ""),
        "skills": profile.get("skills", []),
        "experience_count": len(profile.get("experiences", [])),
        "education_count": len(profile.get("education", [])),
        "summary": profile.get("summary", ""),
    }


# ---------------------------------------------------------------------------
# Interview signal extraction
# ---------------------------------------------------------------------------

@app.post("/api/candidate/interview/extract")
async def extract_interview_signals_endpoint(payload: InterviewInput) -> Dict[str, Any]:
    try:
        signals = await extract_interview_signals(payload.review_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM extraction failed: {exc}")
    return {"interview_type": payload.interview_type, "extracted_signals": signals}


# ---------------------------------------------------------------------------
# Build Candidate Assessment (fusion)
# ---------------------------------------------------------------------------

@app.post("/api/candidate/assessment/build")
async def build_candidate_assessment(payload: dict) -> Dict[str, Any]:
    try:
        return build_fusion_object(
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


# ---------------------------------------------------------------------------
# Synthesis — draft → critic → fairness
# ---------------------------------------------------------------------------

async def _resolve_fairness(report: Dict[str, Any]) -> Dict[str, Any]:
    """Cheap deterministic pre-filter; only call the LLM reviewer if needed."""
    if not needs_llm_fairness_review(report):
        return clean_fairness_result()
    try:
        return await fairness_check(report)
    except Exception:
        return clean_fairness_result()


async def _run_multipass_synthesis(assessment: Dict[str, Any]) -> Dict[str, Any]:
    """Draft → (Critic → Fairness). Returns final report with embedded fairness section.

    In ECONOMY_MODE the critic and fairness passes are skipped to save two of
    the priciest Claude calls; the draft is returned directly.
    """
    draft = await generate_synthesis(assessment)

    if _economy_mode():
        draft["fairness"] = clean_fairness_result()
        return draft

    refined = await critique_and_refine_synthesis(assessment, draft)
    refined["fairness"] = await _resolve_fairness(refined)
    return refined


@app.post("/api/candidate/synthesis/generate")
async def generate_candidate_synthesis(payload: dict) -> Dict[str, Any]:
    """Multi-pass synthesis: draft → critic refinement → fairness review."""
    try:
        return await _run_multipass_synthesis(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM synthesis failed: {exc}")


@app.post("/api/candidate/synthesis/stream")
async def stream_candidate_synthesis(payload: dict) -> StreamingResponse:
    """
    SSE-style stream of the draft synthesis tokens.

    Frontend can render the report as it's being produced.
    Critic + fairness still run server-side after the stream and are
    delivered as a final 'event: final' message containing the refined JSON.
    """

    async def demo_event_source():
        async for delta in demo_service.fake_synthesis_stream():
            yield f"event: delta\ndata: {_json.dumps({'text': delta})}\n\n"
        yield f"event: final\ndata: {_json.dumps(demo_service.demo_synthesis_report())}\n\n"

    async def event_source():
        try:
            buffer_parts = []
            async for delta in generate_synthesis_stream(payload):
                buffer_parts.append(delta)
                # SSE wire format
                yield f"event: delta\ndata: {_json.dumps({'text': delta})}\n\n"

            draft_text = "".join(buffer_parts).strip()
            # Try to parse the draft, fall through if invalid
            try:
                draft_json = _json.loads(draft_text.strip("`").lstrip("json").strip())
            except Exception:
                yield f"event: error\ndata: {_json.dumps({'message': 'draft parse failed'})}\n\n"
                return

            if _economy_mode():
                draft_json["fairness"] = clean_fairness_result()
                yield f"event: final\ndata: {_json.dumps(draft_json)}\n\n"
                return

            refined = await critique_and_refine_synthesis(payload, draft_json)
            refined["fairness"] = await _resolve_fairness(refined)

            yield f"event: final\ndata: {_json.dumps(refined)}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {_json.dumps({'message': str(exc)})}\n\n"

    source = demo_event_source if demo_service.is_demo_mode() else event_source
    return StreamingResponse(source(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Test sheet parsing
# ---------------------------------------------------------------------------

@app.post("/api/test/parse")
async def parse_test_sheet_endpoint(file: UploadFile = File(...)) -> Dict[str, Any]:
    if demo_service.is_demo_mode():
        return demo_service.demo_test_parse()

    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf") or file.content_type == "application/pdf":
        try:
            text = extract_text_from_pdf(content)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}")
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=422, detail="File must be a PDF or UTF-8 text file")

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from file")

    # Try the free deterministic parser first; fall back to Claude only if the
    # layout isn't recognised.
    regex_result = parse_test_sheet_regex(text)
    if regex_result is not None:
        return regex_result

    try:
        return await parse_test_sheet(text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM test parsing failed: {exc}")


# ---------------------------------------------------------------------------
# Pipeline — shared steps 1→5 (CV parse + score, test, interview, fusion)
# ---------------------------------------------------------------------------

async def _build_assessment(
    *,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    candidate_id: str,
    candidate_name: str,
    job_id: str,
    job_title: str,
    target_skills_csv: str,
    test_results_json: str,
    interview_type: str,
    review_text: str,
) -> Dict[str, Any]:
    """Run steps 1→5: parse CV, score, aggregate tests, extract interview, fuse."""
    skills_list = [s.strip() for s in target_skills_csv.split(",") if s.strip()]

    job_record = get_job_by_key(job_id) if job_id else None
    job_for_scoring = job_record or {
        "key": job_id,
        "title": job_title,
        "skills": skills_list,
        "summary": "",
    }
    effective_target_skills = job_for_scoring.get("skills") or skills_list

    try:
        cv_result = await parse_and_score(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            job=job_for_scoring,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CV pipeline error: {exc}")

    cv_matching = cv_result["scoring"]

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

    try:
        interview_signals = await extract_interview_signals(review_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Interview extraction failed: {exc}")

    final_candidate_name = candidate_name or cv_result["profile"].get("full_name", "")
    candidate_context = {"candidate_id": candidate_id, "candidate_name": final_candidate_name}
    job_context = {
        "job_id": job_id,
        "job_title": job_for_scoring.get("title", job_title),
        "target_skills": effective_target_skills,
    }

    return build_fusion_object(
        candidate_context=candidate_context,
        job_context=job_context,
        cv_matching=cv_matching,
        raw_test_scores=raw_scores,
        interview_type=interview_type,
        review_text=review_text,
        interview_signals=interview_signals,
    )


@app.post("/api/candidate/pipeline/prepare")
async def pipeline_prepare(
    file: UploadFile = File(...),
    candidate_id: str = Form(...),
    candidate_name: str = Form(default=""),
    job_id: str = Form(default=""),
    job_title: str = Form(...),
    target_skills: str = Form(default=""),
    test_results_json: str = Form(...),
    interview_type: str = Form(default="technical_interview"),
    review_text: str = Form(...),
) -> Dict[str, Any]:
    """
    Run steps 1-5 only and return the assessment.
    The frontend then opens an SSE stream to /api/candidate/synthesis/stream
    with this assessment to receive the synthesis live.
    """
    if demo_service.is_demo_mode():
        return {"assessment": demo_service.demo_assessment()}

    file_bytes = await file.read()
    assessment = await _build_assessment(
        file_bytes=file_bytes,
        filename=file.filename or "resume",
        content_type=file.content_type or "application/octet-stream",
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        job_id=job_id,
        job_title=job_title,
        target_skills_csv=target_skills,
        test_results_json=test_results_json,
        interview_type=interview_type,
        review_text=review_text,
    )
    return {"assessment": assessment}


@app.post("/api/candidate/full-pipeline")
async def full_pipeline(
    file: UploadFile = File(...),
    candidate_id: str = Form(...),
    candidate_name: str = Form(default=""),
    job_id: str = Form(default=""),
    job_title: str = Form(...),
    target_skills: str = Form(default=""),
    test_results_json: str = Form(...),
    interview_type: str = Form(default="technical_interview"),
    review_text: str = Form(...),
) -> Dict[str, Any]:
    """
    Non-streaming end-to-end pipeline (kept for tests and integrations).
    Steps 1-5 then multi-pass synthesis (draft → critic → fairness).
    """
    if demo_service.is_demo_mode():
        return demo_service.demo_pipeline_result()

    file_bytes = await file.read()
    assessment = await _build_assessment(
        file_bytes=file_bytes,
        filename=file.filename or "resume",
        content_type=file.content_type or "application/octet-stream",
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        job_id=job_id,
        job_title=job_title,
        target_skills_csv=target_skills,
        test_results_json=test_results_json,
        interview_type=interview_type,
        review_text=review_text,
    )

    try:
        report = await _run_multipass_synthesis(assessment)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Synthesis pipeline failed: {exc}")

    return {
        "pipeline_steps": {
            "cv_parsed": True,
            "profile_scored": True,
            "interview_extracted": True,
            "fusion_completed": True,
            "synthesis_generated": True,
            "critic_refined": True,
            "fairness_checked": report.get("fairness", {}).get("status") is not None,
        },
        "assessment": assessment,
        "synthesis_report": report,
    }


# ---------------------------------------------------------------------------
# Jobs list (autocomplete)
# ---------------------------------------------------------------------------

@app.get("/api/jobs/list")
async def jobs_list() -> Dict[str, Any]:
    return {"jobs": get_jobs()}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Static frontend (production)
#
# When the React build is bundled into the image, serve it from the same
# origin so the SPA and /api share host and the frontend can call /api/*
# with relative URLs. Skipped in local dev where the Vite server proxies
# /api to this backend.
# ---------------------------------------------------------------------------

_DEFAULT_STATIC = Path(__file__).resolve().parent.parent / "static"
_STATIC_DIR = Path(os.getenv("STATIC_DIR", str(_DEFAULT_STATIC)))

if _STATIC_DIR.is_dir() and (_STATIC_DIR / "index.html").is_file():
    # Mount nested asset dirs under fixed prefixes so we never collide with /api
    for sub in ("assets", "static"):
        sub_path = _STATIC_DIR / sub
        if sub_path.is_dir():
            app.mount(f"/{sub}", StaticFiles(directory=sub_path), name=f"static-{sub}")

    _INDEX = _STATIC_DIR / "index.html"

    @app.get("/", include_in_schema=False)
    async def _serve_index() -> FileResponse:  # pragma: no cover
        return FileResponse(_INDEX)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:  # pragma: no cover
        # Reserved namespaces handled by real routes above
        if full_path.startswith(("api/", "health")):
            raise HTTPException(status_code=404)
        candidate = _STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_INDEX)
