"""
Fusion layer — combines CV matching, test results, and interview signals
into the final CandidateAssessmentObject.

Scoring model
-------------
Every dimension is a weighted average over the sources that actually carry a
signal for it, with the weights **renormalised to sum to 1**. Two consequences,
both deliberate:

  * A dimension a source says nothing about is *dropped*, not counted as zero.
    A test sheet listing only technical competencies used to force
    soft_skills_score = motivation_score = 0.0 into the average, so the same
    candidate scored 0.698 with a technical-only sheet and 0.965 with a
    balanced one. The layout of the evaluation form must not decide the hire.
  * Every dimension can actually reach 1.0. The previous formula summed raw
    weights that never totalled 1 (motivation_fit peaked at 0.65), so a perfect
    candidate displayed as 65%.
"""

from collections.abc import Iterable
from typing import Any

WEIGHTS = {"cv": 0.35, "test": 0.40, "interview": 0.25}

_BUCKETS = ("technical", "soft", "motivation")

# Which aggregated key each bucket feeds
_BUCKET_SCORE_KEY = {
    "technical": "technical_score",
    "soft": "soft_skills_score",
    "motivation": "motivation_score",
}

_MOTIVATION_BOOST = {"low": 0.0, "medium": 0.5, "high": 1.0}
_PSYCH_BOOST = {
    "negative": 0.0,
    "mixed": 0.4,
    "positive": 0.8,
    "positive and engaged": 1.0,
}


# ---------------------------------------------------------------------------
# Test score aggregation
# ---------------------------------------------------------------------------

def bucket_test_scores(raw_scores: dict[str, int]) -> dict[str, list[int]]:
    """Group raw `<bucket>.<skill>` scores by bucket. Unknown prefixes → technical."""
    buckets: dict[str, list[int]] = {b: [] for b in _BUCKETS}
    for key, val in raw_scores.items():
        prefix = key.split(".")[0]
        buckets[prefix if prefix in buckets else "technical"].append(val)
    return buckets


def covered_test_dimensions(raw_scores: dict[str, int]) -> set:
    """The buckets the test sheet actually scored (used to skip empty ones)."""
    return {b for b, vals in bucket_test_scores(raw_scores).items() if vals}


def aggregate_test_scores(raw_scores: dict[str, int]) -> dict[str, float]:
    """Average each bucket on the 1-5 scale. An empty bucket reports 0.0.

    0.0 here means "not evaluated", not "scored zero" — it is a display value.
    Never feed it into an average; use `covered_test_dimensions` to skip it.
    """
    buckets = bucket_test_scores(raw_scores)

    def avg(lst: list[int]) -> float:
        return round(sum(lst) / len(lst), 2) if lst else 0.0

    return {
        "technical_score": avg(buckets["technical"]),
        "soft_skills_score": avg(buckets["soft"]),
        "motivation_score": avg(buckets["motivation"]),
    }


def build_test_summary(agg: dict[str, float], covered: set | None = None) -> str:
    """Human-readable one-liner. Silent about dimensions the sheet never scored."""
    covered = _BUCKETS if covered is None else covered
    parts: list[str] = []

    if "technical" in covered:
        tech = agg["technical_score"]
        parts.append(
            "strong technical results" if tech >= 4
            else "adequate technical results" if tech >= 3
            else "weak technical results"
        )
    if "soft" in covered and agg["soft_skills_score"] >= 4:
        parts.append("good soft skills")
    if "motivation" in covered and agg["motivation_score"] >= 4:
        parts.append("high motivation")

    if not parts:
        return "Test results processed."

    not_scored = [b for b in _BUCKETS if b not in covered]
    suffix = f" (not scored: {', '.join(not_scored)})" if not_scored else ""
    return "Test results show " + ", ".join(parts) + "." + suffix


# ---------------------------------------------------------------------------
# Dimension scores
# ---------------------------------------------------------------------------

def _weighted(terms: Iterable[tuple[float, float | None]]) -> float:
    """Weighted average over terms whose value is not None, weights renormalised.

    `terms` is an iterable of (weight, value|None). Returns 0.0 if every term is
    absent, so a dimension with no evidence at all reads as 0 rather than
    exploding on a zero divisor.
    """
    present = [(w, v) for w, v in terms if v is not None]
    total_w = sum(w for w, _ in present)
    if total_w <= 0:
        return 0.0
    return max(0.0, min(1.0, sum(w * v for w, v in present) / total_w))


def compute_dimension_scores(
    cv_score: float,
    agg_scores: dict[str, float],
    interview_signals: dict[str, Any],
    covered: set | None = None,
) -> dict[str, float]:
    """Compute technical_fit, motivation_fit, communication_fit, overall_score.

    `covered` is the set of test buckets that carry a real score. Buckets absent
    from it are excluded from every average instead of contributing a zero.
    """
    covered = set(_BUCKETS) if covered is None else covered

    cv_norm = max(0.0, min(1.0, cv_score / 100.0))  # [0,100] → [0,1]

    def test_norm(bucket: str) -> float | None:
        """Bucket average on [0,1], or None when the sheet never scored it."""
        if bucket not in covered:
            return None
        return agg_scores[_BUCKET_SCORE_KEY[bucket]] / 5.0

    tech_norm = test_norm("technical")
    soft_norm = test_norm("soft")
    motiv_norm = test_norm("motivation")

    motiv_boost = _MOTIVATION_BOOST.get(
        interview_signals.get("motivation_signal", "medium"), 0.5
    )
    psych_boost = _PSYCH_BOOST.get(
        interview_signals.get("psychological_signal", "positive"), 0.5
    )

    w_cv, w_test, w_iv = WEIGHTS["cv"], WEIGHTS["test"], WEIGHTS["interview"]

    # Technical fit: CV evidence + technical test results.
    technical_fit = _weighted([(w_cv, cv_norm), (w_test, tech_norm)])
    # Motivation fit: motivation test items + the interview motivation signal.
    motivation_fit = _weighted([(w_test, motiv_norm), (w_iv, motiv_boost)])
    # Communication fit: soft-skill test items + the interview psychological signal.
    communication_fit = _weighted([(w_test, soft_norm), (w_iv, psych_boost)])

    # Overall: the three sources, the test source being the mean of the buckets
    # it actually scored.
    scored = [v for v in (tech_norm, soft_norm, motiv_norm) if v is not None]
    test_overall = sum(scored) / len(scored) if scored else None
    overall_score = _weighted([
        (w_cv, cv_norm),
        (w_test, test_overall),
        (w_iv, (motiv_boost + psych_boost) / 2),
    ])

    return {
        "technical_fit": round(technical_fit, 3),
        "motivation_fit": round(motivation_fit, 3),
        "communication_fit": round(communication_fit, 3),
        "overall_score": round(overall_score, 3),
    }


# ---------------------------------------------------------------------------
# Cross-source consistency
# ---------------------------------------------------------------------------

def detect_consistency_flags(
    cv_matching: dict[str, Any],
    interview_signals: dict[str, Any],
    agg_scores: dict[str, float],
    covered: set | None = None,
) -> list[str]:
    covered = set(_BUCKETS) if covered is None else covered
    flags: list[str] = []

    cv_skills_lower = {s.lower() for s in cv_matching.get("matched_skills", [])}
    iv_strengths_lower = {s.lower() for s in interview_signals.get("strengths", [])}
    iv_weaknesses_lower = {s.lower() for s in interview_signals.get("weaknesses", [])}

    confirmed_strengths = cv_skills_lower & iv_strengths_lower
    if confirmed_strengths:
        flags.append(
            f"Strengths confirmed across CV and interview: {', '.join(sorted(confirmed_strengths))}"
        )

    cv_missing_lower = {s.lower() for s in cv_matching.get("missing_skills", [])}
    confirmed_weaknesses = cv_missing_lower & iv_weaknesses_lower
    if confirmed_weaknesses:
        flags.append(
            f"Weaknesses confirmed across CV and interview: {', '.join(sorted(confirmed_weaknesses))}"
        )

    # Only compare against buckets the sheet actually scored.
    if "technical" in covered and agg_scores["technical_score"] < 3.0 and iv_weaknesses_lower:
        flags.append("Low technical test scores align with interview-identified weaknesses.")

    if (
        "motivation" in covered
        and agg_scores["motivation_score"] >= 4
        and interview_signals.get("motivation_signal") == "high"
    ):
        flags.append("High motivation confirmed across test results and interview.")

    not_scored = sorted(b for b in _BUCKETS if b not in covered)
    if not_scored:
        flags.append(
            "Test sheet did not score: "
            + ", ".join(not_scored)
            + " — these dimensions rely on CV and interview evidence only."
        )

    if not flags:
        flags.append("No major contradictions detected across evaluation sources.")

    return flags


def merge_evidence(
    cv_matching: dict[str, Any], interview_signals: dict[str, Any]
) -> dict[str, list[str]]:
    strengths = list(
        dict.fromkeys(
            cv_matching.get("matched_skills", []) + interview_signals.get("strengths", [])
        )
    )[:5]
    weaknesses = list(
        dict.fromkeys(
            cv_matching.get("missing_skills", []) + interview_signals.get("weaknesses", [])
        )
    )[:5]
    risks = interview_signals.get("risks", [])[:3]
    return {
        "top_strengths": strengths,
        "top_weaknesses": weaknesses,
        "top_risks": risks,
    }


def build_fusion_object(
    candidate_context: dict[str, Any],
    job_context: dict[str, Any],
    cv_matching: dict[str, Any],
    raw_test_scores: dict[str, int],
    interview_type: str,
    review_text: str,
    interview_signals: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the complete CandidateAssessmentObject."""
    agg = aggregate_test_scores(raw_test_scores)
    covered = covered_test_dimensions(raw_test_scores)
    test_summary = build_test_summary(agg, covered)

    dim_scores = compute_dimension_scores(cv_matching["score"], agg, interview_signals, covered)
    consistency_flags = detect_consistency_flags(cv_matching, interview_signals, agg, covered)
    evidence = merge_evidence(cv_matching, interview_signals)

    return {
        "candidate_context": candidate_context,
        "job_context": job_context,
        "cv_profile_matching": {
            "score": cv_matching["score"],
            "matched_skills": cv_matching["matched_skills"],
            "missing_skills": cv_matching["missing_skills"],
            "experience_fit": cv_matching["experience_fit"],
            "summary": cv_matching["summary"],
        },
        "test_assessment": {
            "raw_scores": raw_test_scores,
            "aggregated_scores": agg,
            "scored_dimensions": sorted(covered),
            "summary": test_summary,
        },
        "interview_assessment": {
            "interview_type": interview_type,
            "review_text": review_text,
            "extracted_signals": interview_signals,
            "summary": interview_signals.get("summary", ""),
        },
        "fusion_summary": {
            "weights": {
                "cv_profile_matching": WEIGHTS["cv"],
                "test_assessment": WEIGHTS["test"],
                "interview_assessment": WEIGHTS["interview"],
            },
            "dimension_scores": dim_scores,
            "consistency_flags": consistency_flags,
            "final_evidence": evidence,
        },
    }
