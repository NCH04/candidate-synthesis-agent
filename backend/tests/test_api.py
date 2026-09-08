"""API contract, guardrails and SSE protocol — all under DEMO_MODE (no API calls)."""

import json


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_config_reports_demo_mode(client):
    body = client.get("/api/config").json()
    assert body["demo_mode"] is True
    # The configured tiers are surfaced so the UI can show them; the values
    # themselves come from the environment (see test_llm_service for defaults).
    assert body["models"]["fast"] and body["models"]["smart"]


def test_jobs_list(client):
    jobs = client.get("/api/jobs/list").json()["jobs"]
    assert len(jobs) == 10
    assert all({"key", "title", "skills"} <= set(j) for j in jobs)


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------

def test_synthesis_stream_rejects_an_arbitrary_payload(client, monkeypatch):
    """The stream endpoint feeds its body to Claude — it must not accept junk.

    Without validation this route is an open, unauthenticated LLM proxy.
    """
    import main

    monkeypatch.setattr(main.demo_service, "is_demo_mode", lambda: False)
    res = client.post("/api/candidate/synthesis/stream", json={"ignore": "previous instructions"})
    assert res.status_code == 422


def test_synthesis_generate_rejects_an_arbitrary_payload(client, monkeypatch):
    import main

    monkeypatch.setattr(main.demo_service, "is_demo_mode", lambda: False)
    res = client.post("/api/candidate/synthesis/generate", json={"hello": "world"})
    assert res.status_code == 422


def test_oversized_upload_is_refused(client, monkeypatch):
    import main

    monkeypatch.setattr(main.demo_service, "is_demo_mode", lambda: False)
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 1024)
    big = b"x" * 5000
    res = client.post("/api/cv/parse", files={"file": ("cv.txt", big, "text/plain")})
    assert res.status_code == 413


def test_rate_limit_kicks_in(client, monkeypatch):
    import main

    monkeypatch.setattr(main, "RATE_LIMIT_PER_MINUTE", 3)
    main._rate_buckets.clear()
    codes = [
        client.post("/api/test/parse", files={"file": ("t.txt", b"x", "text/plain")}).status_code
        for _ in range(5)
    ]
    assert 429 in codes
    main._rate_buckets.clear()


def test_api_key_is_enforced_when_configured(client, monkeypatch):
    import main

    monkeypatch.setattr(main, "APP_API_KEY", "s3cret")
    assert client.post("/api/test/parse", files={"file": ("t.txt", b"x", "text/plain")}).status_code == 401
    ok = client.post(
        "/api/test/parse",
        files={"file": ("t.txt", b"x", "text/plain")},
        headers={"X-API-Key": "s3cret"},
    )
    assert ok.status_code == 200


def test_cors_never_pairs_wildcard_with_credentials():
    """`allow_origins=["*"]` + credentials is rejected by every browser."""
    import main

    if main.ALLOWED_ORIGINS == ["*"]:
        assert main._wildcard_origins is True


# ---------------------------------------------------------------------------
# Demo pipeline + SSE protocol
# ---------------------------------------------------------------------------

def test_demo_pipeline_prepare_returns_a_valid_assessment(client):
    from schemas import CandidateAssessmentObject

    res = client.post(
        "/api/candidate/pipeline/prepare",
        files={"file": ("cv.txt", b"demo cv", "text/plain")},
        data={
            "candidate_id": "c1",
            "job_title": "Senior Python Backend Engineer",
            "test_results_json": '{"technical.python": 4}',
            "review_text": "Demo candidate.",
        },
    )
    assert res.status_code == 200
    CandidateAssessmentObject.model_validate(res.json()["assessment"])


def test_demo_stream_emits_phases_then_a_final_report(client):
    from schemas import CandidateSynthesisReport

    with client.stream(
        "POST", "/api/candidate/synthesis/stream", json={"any": "payload"}
    ) as res:
        assert res.status_code == 200
        body = "".join(res.iter_text())

    events, final_payload = [], None
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        lines = frame.split("\n")
        name = next(x[7:].strip() for x in lines if x.startswith("event: "))
        data = "".join(x[6:] for x in lines if x.startswith("data: "))
        events.append(name)
        if name == "final":
            final_payload = json.loads(data)

    # Real server-driven phases, not client-side timers.
    assert "phase" in events
    assert events[-1] == "final"
    assert "delta" in events
    CandidateSynthesisReport.model_validate(final_payload)


def test_demo_full_pipeline_matches_its_response_model(client):
    from schemas import FullPipelineResponse

    res = client.post(
        "/api/candidate/full-pipeline",
        files={"file": ("cv.txt", b"demo cv", "text/plain")},
        data={
            "candidate_id": "c1",
            "job_title": "Senior Python Backend Engineer",
            "test_results_json": '{"technical.python": 4}',
            "review_text": "Demo candidate.",
        },
    )
    assert res.status_code == 200
    FullPipelineResponse.model_validate(res.json())
