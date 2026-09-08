"""Scoring must depend on the candidate, not on how the test sheet is laid out."""

import pytest
from services.fusion_service import (
    aggregate_test_scores,
    build_fusion_object,
    compute_dimension_scores,
    covered_test_dimensions,
    detect_consistency_flags,
)

STRONG_SIGNALS = {
    "motivation_signal": "high",
    "psychological_signal": "positive and engaged",
    "strengths": [],
    "weaknesses": [],
    "risks": [],
    "summary": "",
}
WEAK_SIGNALS = {
    "motivation_signal": "low",
    "psychological_signal": "negative",
    "strengths": [],
    "weaknesses": [],
    "risks": [],
    "summary": "",
}


def _dims(raw, cv=90.0, signals=STRONG_SIGNALS):
    agg = aggregate_test_scores(raw)
    return compute_dimension_scores(cv, agg, signals, covered_test_dimensions(raw))


# ---------------------------------------------------------------------------
# The regression this suite exists for
# ---------------------------------------------------------------------------

def test_sheet_layout_does_not_change_the_score():
    """Same candidate, two sheet layouts, same overall score.

    Empty buckets used to be averaged in as 0.0, so a technical-only sheet
    scored 0.698 where a balanced sheet scored 0.965 — the form decided the hire.
    """
    tech_only = {"technical.python": 5, "technical.sql": 5, "technical.docker": 5}
    balanced = {"technical.python": 5, "soft.communication": 5, "motivation.interest": 5}
    assert _dims(tech_only)["overall_score"] == _dims(balanced)["overall_score"]


def test_unscored_dimension_is_excluded_not_zeroed():
    dims = _dims({"technical.python": 5})
    # Motivation was never tested, so it rests entirely on the interview signal.
    assert dims["motivation_fit"] == 1.0
    assert dims["communication_fit"] == 1.0


def test_perfect_candidate_reaches_one():
    """Every dimension must be able to reach 1.0.

    The old formula summed raw weights that never totalled 1, so a perfect
    candidate displayed as motivation_fit = 0.65.
    """
    dims = _dims({"technical.python": 5, "soft.communication": 5, "motivation.interest": 5}, cv=100.0)
    assert dims["technical_fit"] == 1.0
    assert dims["motivation_fit"] == 1.0
    assert dims["communication_fit"] == 1.0
    assert dims["overall_score"] == 1.0


def test_worst_candidate_stays_low():
    dims = _dims({"technical.python": 1, "soft.communication": 1, "motivation.interest": 1},
                 cv=0.0, signals=WEAK_SIGNALS)
    assert all(0.0 <= v <= 0.25 for v in dims.values())


@pytest.mark.parametrize("raw", [
    {},
    {"technical.python": 3},
    {"soft.communication": 3},
    {"motivation.interest": 3},
    {"unknown_prefix_skill": 3},
])
def test_scores_always_within_bounds(raw):
    for value in _dims(raw, cv=50.0).values():
        assert 0.0 <= value <= 1.0


def test_no_evidence_at_all_does_not_divide_by_zero():
    dims = compute_dimension_scores(0.0, aggregate_test_scores({}), {}, set())
    assert dims["technical_fit"] == 0.0


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def test_unknown_prefix_falls_back_to_technical():
    assert covered_test_dimensions({"mystery.skill": 4}) == {"technical"}


def test_aggregated_zero_means_not_evaluated():
    agg = aggregate_test_scores({"technical.python": 4})
    assert agg["technical_score"] == 4.0
    assert agg["soft_skills_score"] == 0.0
    assert "soft" not in covered_test_dimensions({"technical.python": 4})


def test_consistency_flags_report_unscored_dimensions():
    flags = detect_consistency_flags(
        {"matched_skills": [], "missing_skills": []},
        STRONG_SIGNALS,
        aggregate_test_scores({"technical.python": 4}),
        {"technical"},
    )
    assert any("did not score" in f for f in flags)


def test_consistency_flags_do_not_fire_on_unscored_dimensions():
    """A motivation bucket that was never scored must not produce a motivation flag."""
    flags = detect_consistency_flags(
        {"matched_skills": [], "missing_skills": []},
        STRONG_SIGNALS,
        aggregate_test_scores({"technical.python": 4}),
        {"technical"},
    )
    assert not any("High motivation confirmed" in f for f in flags)


# ---------------------------------------------------------------------------
# Full fusion object
# ---------------------------------------------------------------------------

def test_build_fusion_object_matches_the_assessment_schema():
    from schemas import CandidateAssessmentObject

    obj = build_fusion_object(
        candidate_context={"candidate_id": "c1", "candidate_name": "Alex Doe"},
        job_context={"job_id": "j1", "job_title": "Backend Engineer", "target_skills": ["Python"]},
        cv_matching={
            "score": 78.0,
            "matched_skills": ["Python"],
            "missing_skills": ["Kubernetes"],
            "experience_fit": "Good",
            "summary": "Solid fit.",
        },
        raw_test_scores={"technical.python": 4, "soft.communication": 4},
        interview_type="technical_interview",
        review_text="Strong candidate overall.",
        interview_signals=STRONG_SIGNALS,
    )
    CandidateAssessmentObject.model_validate(obj)
    assert obj["test_assessment"]["scored_dimensions"] == ["soft", "technical"]
