"""
Fusion layer — combines CV matching, test results, and interview signals
into the final CandidateAssessmentObject.
"""

from typing import Any, Dict, List

WEIGHTS = {"cv": 0.35, "test": 0.40, "interview": 0.25}

_TECHNICAL_KEYS = [k for k in ["technical"] if k]  # prefix matching below
_SOFT_KEYS = ["soft"]
_MOTIVATION_KEYS = ["motivation"]


def aggregate_test_scores(raw_scores: Dict[str, int]) -> Dict[str, float]:
    """Group raw test scores into technical / soft / motivation dimensions."""
    buckets: Dict[str, List[int]] = {"technical": [], "soft": [], "motivation": []}

    for key, val in raw_scores.items():
        prefix = key.split(".")[0]
        if prefix in buckets:
            buckets[prefix].append(val)
        else:
            buckets["technical"].append(val)

    def avg(lst: List[int]) -> float:
        return round(sum(lst) / len(lst), 2) if lst else 0.0

    return {
        "technical_score": avg(buckets["technical"]),
        "soft_skills_score": avg(buckets["soft"]),
        "motivation_score": avg(buckets["motivation"]),
    }


def build_test_summary(agg: Dict[str, float]) -> str:
    parts = []
    if agg["technical_score"] >= 4:
        parts.append("strong technical results")
    elif agg["technical_score"] >= 3:
        parts.append("adequate technical results")
    else:
        parts.append("weak technical results")

    if agg["soft_skills_score"] >= 4:
        parts.append("good soft skills")
    if agg["motivation_score"] >= 4:
        parts.append("high motivation")

    return "Test results show " + ", ".join(parts) + "." if parts else "Test results processed."


def compute_dimension_scores(
    cv_score: float,
    agg_scores: Dict[str, float],
    interview_signals: Dict[str, Any],
) -> Dict[str, float]:
    """Compute technical_fit, motivation_fit, communication_fit, overall_score."""
    # Normalize CV score from [0,100] to [0,1]
    cv_norm = cv_score / 100.0

    # Normalize test scores from [0,5] to [0,1]
    tech_norm = agg_scores["technical_score"] / 5.0
    soft_norm = agg_scores["soft_skills_score"] / 5.0
    motiv_norm = agg_scores["motivation_score"] / 5.0

    # Interview boost factors
    motiv_signal = interview_signals.get("motivation_signal", "medium")
    motiv_boost = {"low": 0.0, "medium": 0.5, "high": 1.0}.get(motiv_signal, 0.5)

    psych_signal = interview_signals.get("psychological_signal", "positive")
    psych_boost = {
        "negative": 0.0,
        "mixed": 0.4,
        "positive": 0.8,
        "positive and engaged": 1.0,
    }.get(psych_signal, 0.5)

    technical_fit = round(
        WEIGHTS["cv"] * cv_norm + WEIGHTS["test"] * tech_norm + WEIGHTS["interview"] * 0.5,
        3,
    )
    motivation_fit = round(
        WEIGHTS["test"] * motiv_norm + WEIGHTS["interview"] * motiv_boost,
        3,
    )
    communication_fit = round(
        WEIGHTS["test"] * soft_norm + WEIGHTS["interview"] * psych_boost,
        3,
    )
    overall_score = round(
        WEIGHTS["cv"] * cv_norm
        + WEIGHTS["test"] * ((tech_norm + soft_norm + motiv_norm) / 3)
        + WEIGHTS["interview"] * ((motiv_boost + psych_boost) / 2),
        3,
    )

    # Clamp to [0, 1]
    def clamp(v: float) -> float:
        return max(0.0, min(1.0, v))

    return {
        "technical_fit": clamp(technical_fit),
        "motivation_fit": clamp(motivation_fit),
        "communication_fit": clamp(communication_fit),
        "overall_score": clamp(overall_score),
    }


def detect_consistency_flags(
    cv_matching: Dict[str, Any],
    interview_signals: Dict[str, Any],
    agg_scores: Dict[str, float],
) -> List[str]:
    flags: List[str] = []

    cv_skills_lower = {s.lower() for s in cv_matching.get("matched_skills", [])}
    iv_strengths_lower = {s.lower() for s in interview_signals.get("strengths", [])}
    iv_weaknesses_lower = {s.lower() for s in interview_signals.get("weaknesses", [])}

    # Positive convergence
    confirmed_strengths = cv_skills_lower & iv_strengths_lower
    if confirmed_strengths:
        flags.append(
            f"Strengths confirmed across CV and interview: {', '.join(confirmed_strengths)}"
        )

    # Weakness convergence
    cv_missing_lower = {s.lower() for s in cv_matching.get("missing_skills", [])}
    confirmed_weaknesses = cv_missing_lower & iv_weaknesses_lower
    if confirmed_weaknesses:
        flags.append(
            f"Weaknesses confirmed across CV and interview: {', '.join(confirmed_weaknesses)}"
        )

    # Low test score + interview weakness
    if agg_scores["technical_score"] < 3.0 and iv_weaknesses_lower:
        flags.append("Low technical test scores align with interview-identified weaknesses.")

    # High motivation from both sources
    if (
        agg_scores.get("motivation_score", 0) >= 4
        and interview_signals.get("motivation_signal") == "high"
    ):
        flags.append("High motivation confirmed across test results and interview.")

    if not flags:
        flags.append("No major contradictions detected across evaluation sources.")

    return flags


def merge_evidence(
    cv_matching: Dict[str, Any], interview_signals: Dict[str, Any]
) -> Dict[str, List[str]]:
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
    candidate_context: Dict[str, Any],
    job_context: Dict[str, Any],
    cv_matching: Dict[str, Any],
    raw_test_scores: Dict[str, int],
    interview_type: str,
    review_text: str,
    interview_signals: Dict[str, Any],
) -> Dict[str, Any]:
    """Assemble the complete CandidateAssessmentObject."""
    agg = aggregate_test_scores(raw_test_scores)
    test_summary = build_test_summary(agg)

    dim_scores = compute_dimension_scores(
        cv_matching["score"], agg, interview_signals
    )
    consistency_flags = detect_consistency_flags(cv_matching, interview_signals, agg)
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
