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

Hardening for public deployment (all opt-in via env, see .env.example):
  * APP_API_KEY      — when set, every /api route requires an X-API-Key header.
  * ALLOWED_ORIGINS  — CORS allow-list; `*` disables credentialed CORS.
  * MAX_UPLOAD_MB    — uploads are streamed and rejected past this size.
  * RATE_LIMIT_PER_MINUTE — per-IP sliding window on the expensive routes.
"""

from __future__ import annotations

import json as _json
import os
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

try:
    from .schemas import (
        AppConfigResponse,
        AssessmentResponse,
        CandidateAssessmentObject,
        CandidateSynthesisReport,
        CVParseResponse,
        FullPipelineResponse,
        InterviewInput,
        JobsListResponse,
        TestSheetParseResult,
    )
    from .services import demo_service
    from .services.cv_service import extract_text_from_pdf, parse_and_score, parse_cv
    from .services.fairness_service import clean_fairness_result, needs_llm_fairness_review
    from .services.fusion_service import build_fusion_object
    from .services.jobs_service import get_job_by_key, get_jobs, load_jobs_from_file
    from .services.llm_service import (
        FAST_MODEL,
        SMART_MODEL,
        LLMOutputError,
        critique_and_refine_synthesis,
        extract_interview_signals,
        fairness_check,
        generate_synthesis,
        generate_synthesis_stream,
        parse_json_response,
        parse_test_sheet,
    )
    from .services.test_parser_service import parse_test_sheet_regex
except ImportError:
    from schemas import (  # type: ignore
        AppConfigResponse,
        AssessmentResponse,
        CandidateAssessmentObject,
        CandidateSynthesisReport,
        CVParseResponse,
        FullPipelineResponse,
        InterviewInput,
        JobsListResponse,
        TestSheetParseResult,
    )
    from services import demo_service  # type: ignore
    from services.cv_service import extract_text_from_pdf, parse_and_score, parse_cv  # type: ignore
    from services.fairness_service import (  # type: ignore
        clean_fairness_result,
        needs_llm_fairness_review,
    )
    from services.fusion_service import build_fusion_object  # type: ignore
    from services.jobs_service import get_job_by_key, get_jobs, load_jobs_from_file  # type: ignore
    from services.llm_service import (  # type: ignore
        FAST_MODEL,
        SMART_MODEL,
        LLMOutputError,
        critique_and_refine_synthesis,
        extract_interview_signals,
        fairness_check,
        generate_synthesis,
        generate_synthesis_stream,
        parse_json_response,
        parse_test_sheet,
    )
    from services.test_parser_service import parse_test_sheet_regex  # type: ignore


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _economy_mode() -> bool:
    """When true, skip the critic + fairness passes (the two priciest steps)."""
    return _flag("ECONOMY_MODE")


MAX_UPLOAD_BYTES = int(float(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
APP_API_KEY = os.getenv("APP_API_KEY", "").strip()
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load jobs from local JSON file on startup."""
    load_jobs_from_file()
    yield


app = FastAPI(title="AI Candidate Synthesis Agent", version="2.1.0", lifespan=lifespan)

# `allow_credentials=True` alongside `allow_origins=["*"]` is rejected by every
# browser — the wildcard and credentials are mutually exclusive in the CORS
# spec. Send credentials only when a concrete allow-list is configured.
_wildcard_origins = ALLOWED_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=not _wildcard_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# ---------------------------------------------------------------------------
# Auth + rate limiting
#
# Both are no-ops until configured, so local dev and the demo deployment are
# unchanged. Without them, every endpoint below is an unauthenticated proxy to
# a paid Claude account.
# ---------------------------------------------------------------------------

async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Reject the request unless it carries the configured key.

    No key configured → open access (local dev, demo deployments).
    """
    if not APP_API_KEY:
        return
    if x_api_key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


async def rate_limit(request: Request) -> None:
    """Per-IP sliding window over the last 60 seconds.

    In-memory and therefore per-process: it is a guardrail against casual abuse
    and runaway cost on a single-container deployment, not a distributed quota.
    """
    if RATE_LIMIT_PER_MINUTE <= 0:
        return
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_buckets[client_ip]
    while bucket and now - bucket[0] > 60.0:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({RATE_LIMIT_PER_MINUTE}/min). Try again shortly.",
        )
    bucket.append(now)


# Applied to every route that can trigger a paid Claude call or a file upload.
GUARDED = [Depends(require_api_key), Depends(rate_limit)]


async def read_upload(file: UploadFile) -> bytes:
    """Read an upload in chunks, refusing anything past MAX_UPLOAD_BYTES.

    `await file.read()` with no limit lets a single request pull an arbitrarily
    large body into memory.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (limit {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
            )
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    return b"".join(chunks)


def _sse(event: str, payload: dict[str, Any]) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {_json.dumps(payload, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Runtime config (so the frontend can show a demo banner, etc.)
# ---------------------------------------------------------------------------

@app.get("/api/config", response_model=AppConfigResponse)
async def get_config() -> dict[str, Any]:
    return {
        "demo_mode": demo_service.is_demo_mode(),
        "economy_mode": _economy_mode(),
        "models": {"fast": FAST_MODEL, "smart": SMART_MODEL},
    }


# ---------------------------------------------------------------------------
# CV — parse only (used at upload time to auto-fill candidate name/skills)
# ---------------------------------------------------------------------------

@app.post("/api/cv/parse", response_model=CVParseResponse, dependencies=GUARDED)
async def parse_cv_endpoint(file: UploadFile = File(...)) -> dict[str, Any]:
    """Parse a CV file via Claude and return a structured profile."""
    if demo_service.is_demo_mode():
        return demo_service.demo_cv_parse()

    content = await read_upload(file)
    try:
        profile = await parse_cv(
            file_bytes=content,
            filename=file.filename or "resume",
            content_type=file.content_type or "application/octet-stream",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CV parsing failed: {exc}") from exc

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

@app.post("/api/candidate/interview/extract", dependencies=GUARDED)
async def extract_interview_signals_endpoint(payload: InterviewInput) -> dict[str, Any]:
    try:
        signals = await extract_interview_signals(payload.review_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM extraction failed: {exc}") from exc
    return {"interview_type": payload.interview_type, "extracted_signals": signals}


# ---------------------------------------------------------------------------
# Build Candidate Assessment (fusion)
# ---------------------------------------------------------------------------

@app.post("/api/candidate/assessment/build", response_model=CandidateAssessmentObject)
async def build_candidate_assessment(payload: dict) -> dict[str, Any]:
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
        raise HTTPException(status_code=422, detail=f"Missing field: {exc}") from exc


# ---------------------------------------------------------------------------
# Synthesis — draft → critic → fairness
# ---------------------------------------------------------------------------

async def _resolve_fairness(report: dict[str, Any]) -> dict[str, Any]:
    """Cheap deterministic pre-filter; only call the LLM reviewer if needed."""
    if not needs_llm_fairness_review(report):
        return clean_fairness_result()
    try:
        return await fairness_check(report)
    except Exception:
        return clean_fairness_result()


async def _run_multipass_synthesis(assessment: dict[str, Any]) -> dict[str, Any]:
    """Draft → (Critic → Fairness). Returns final report with embedded fairness section.

    In ECONOMY_MODE the critic pass is skipped to save the priciest Claude call.
    The fairness review is never skipped: it is a compliance guardrail, and the
    deterministic pre-filter already makes it free on a clean report.
    """
    draft = await generate_synthesis(assessment)

    if _economy_mode():
        draft["fairness"] = await _resolve_fairness(draft)
        return draft

    refined = await critique_and_refine_synthesis(assessment, draft)
    refined["fairness"] = await _resolve_fairness(refined)
    return refined


def _validated_assessment(payload: dict[str, Any]) -> dict[str, Any]:
    """Reject anything that is not a real assessment object.

    This endpoint feeds its payload straight to Claude, so without validation it
    is an open prompt-injection surface and a free LLM proxy.
    """
    try:
        CandidateAssessmentObject.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid assessment object: {exc}") from exc
    return payload


@app.post(
    "/api/candidate/synthesis/generate",
    response_model=CandidateSynthesisReport,
    dependencies=GUARDED,
)
async def generate_candidate_synthesis(payload: dict) -> dict[str, Any]:
    """Multi-pass synthesis: draft → critic refinement → fairness review."""
    try:
        return await _run_multipass_synthesis(_validated_assessment(payload))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM synthesis failed: {exc}") from exc


@app.post("/api/candidate/synthesis/stream", dependencies=GUARDED)
async def stream_candidate_synthesis(payload: dict) -> StreamingResponse:
    """
    SSE stream of the synthesis.

    Events:
      phase  — {"phase": "draft"|"critic"|"fairness"|"done"} — real server state,
               so the UI never has to guess with timers.
      delta  — {"text": "..."} — draft tokens as they arrive.
      final  — the refined, fairness-checked report.
      error  — {"message": "..."}
    """
    assessment = _validated_assessment(payload) if not demo_service.is_demo_mode() else payload

    async def demo_event_source() -> AsyncIterator[str]:
        yield _sse("phase", {"phase": "draft"})
        async for delta in demo_service.fake_synthesis_stream():
            yield _sse("delta", {"text": delta})
        yield _sse("phase", {"phase": "critic"})
        yield _sse("phase", {"phase": "fairness"})
        yield _sse("phase", {"phase": "done"})
        yield _sse("final", demo_service.demo_synthesis_report())

    async def event_source() -> AsyncIterator[str]:
        try:
            yield _sse("phase", {"phase": "draft"})
            buffer_parts: list[str] = []
            async for delta in generate_synthesis_stream(assessment):
                buffer_parts.append(delta)
                yield _sse("delta", {"text": delta})

            draft_text = "".join(buffer_parts)
            try:
                draft_json = parse_json_response(draft_text)
            except LLMOutputError:
                # The streamed draft was malformed. Rather than discard a run the
                # user already paid for, redo the draft non-streamed — that path
                # validates against the schema and retries once on its own.
                yield _sse("phase", {"phase": "draft-retry"})
                try:
                    draft_json = await generate_synthesis(assessment)
                except Exception as exc:
                    yield _sse("error", {"message": f"draft failed: {exc}"})
                    return

            if _economy_mode():
                yield _sse("phase", {"phase": "fairness"})
                draft_json["fairness"] = await _resolve_fairness(draft_json)
                yield _sse("phase", {"phase": "done"})
                yield _sse("final", draft_json)
                return

            yield _sse("phase", {"phase": "critic"})
            refined = await critique_and_refine_synthesis(assessment, draft_json)

            yield _sse("phase", {"phase": "fairness"})
            refined["fairness"] = await _resolve_fairness(refined)

            yield _sse("phase", {"phase": "done"})
            yield _sse("final", refined)
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})

    source = demo_event_source if demo_service.is_demo_mode() else event_source
    return StreamingResponse(
        source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Test sheet parsing
# ---------------------------------------------------------------------------

@app.post("/api/test/parse", response_model=TestSheetParseResult, dependencies=GUARDED)
async def parse_test_sheet_endpoint(file: UploadFile = File(...)) -> dict[str, Any]:
    if demo_service.is_demo_mode():
        return demo_service.demo_test_parse()

    content = await read_upload(file)
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf") or file.content_type == "application/pdf":
        try:
            text = extract_text_from_pdf(content)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}") from exc
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=422, detail="File must be a PDF or UTF-8 text file"
            ) from exc

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
        raise HTTPException(status_code=502, detail=f"LLM test parsing failed: {exc}") from exc


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
) -> dict[str, Any]:
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
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CV pipeline error: {exc}") from exc

    cv_matching = cv_result["scoring"]

    try:
        raw_scores: dict[str, int] = _json.loads(test_results_json)
        if not isinstance(raw_scores, dict):
            raise ValueError("test_results_json must be a JSON object")
        if not raw_scores:
            raise ValueError("test_results_json must contain at least one score")
        for k, v in raw_scores.items():
            if not (1 <= int(v) <= 5):
                raise ValueError(f"Score for '{k}' must be between 1 and 5")
        raw_scores = {k: int(v) for k, v in raw_scores.items()}
    except (TypeError, ValueError, _json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid test_results_json: {exc}") from exc

    try:
        interview_signals = await extract_interview_signals(review_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Interview extraction failed: {exc}") from exc

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


@app.post(
    "/api/candidate/pipeline/prepare",
    response_model=AssessmentResponse,
    dependencies=GUARDED,
)
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
) -> dict[str, Any]:
    """
    Run steps 1-5 only and return the assessment.
    The frontend then opens an SSE stream to /api/candidate/synthesis/stream
    with this assessment to receive the synthesis live.
    """
    if demo_service.is_demo_mode():
        return {"assessment": demo_service.demo_assessment()}

    file_bytes = await read_upload(file)
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


@app.post(
    "/api/candidate/full-pipeline",
    response_model=FullPipelineResponse,
    dependencies=GUARDED,
)
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
) -> dict[str, Any]:
    """
    Non-streaming end-to-end pipeline (kept for tests and integrations).
    Steps 1-5 then multi-pass synthesis (draft → critic → fairness).
    """
    if demo_service.is_demo_mode():
        return demo_service.demo_pipeline_result()

    file_bytes = await read_upload(file)
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
        raise HTTPException(status_code=502, detail=f"Synthesis pipeline failed: {exc}") from exc

    return {
        "pipeline_steps": {
            "cv_parsed": True,
            "profile_scored": True,
            "interview_extracted": True,
            "fusion_completed": True,
            "synthesis_generated": True,
            "critic_refined": not _economy_mode(),
            "fairness_checked": report.get("fairness", {}).get("status") is not None,
        },
        "assessment": assessment,
        "synthesis_report": report,
    }


# ---------------------------------------------------------------------------
# Jobs list (autocomplete)
# ---------------------------------------------------------------------------

@app.get("/api/jobs/list", response_model=JobsListResponse)
async def jobs_list() -> dict[str, Any]:
    return {"jobs": get_jobs()}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
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
_STATIC_DIR = Path(os.getenv("STATIC_DIR", str(_DEFAULT_STATIC))).resolve()

if _STATIC_DIR.is_dir() and (_STATIC_DIR / "index.html").is_file():
    # Mount nested asset dirs under fixed prefixes so we never collide with /api
    for sub in ("assets", "static"):
        sub_path = _STATIC_DIR / sub
        if sub_path.is_dir():
            app.mount(f"/{sub}", StaticFiles(directory=sub_path), name=f"static-{sub}")

    _INDEX = _STATIC_DIR / "index.html"

    def _safe_static_path(full_path: str) -> Path | None:
        """Resolve a request path inside the static dir, or None if it escapes.

        Joining an unchecked path param onto a directory lets `../` walk out of
        it and serve arbitrary files; resolving and re-checking containment is
        what stops that.
        """
        try:
            candidate = (_STATIC_DIR / full_path).resolve()
        except (OSError, ValueError):
            return None
        if candidate == _STATIC_DIR or _STATIC_DIR in candidate.parents:
            return candidate
        return None

    @app.get("/", include_in_schema=False)
    async def _serve_index() -> FileResponse:  # pragma: no cover
        return FileResponse(_INDEX)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:  # pragma: no cover
        # Reserved namespaces handled by real routes above
        if full_path.startswith(("api/", "health")):
            raise HTTPException(status_code=404)
        candidate = _safe_static_path(full_path)
        if candidate is not None and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_INDEX)
