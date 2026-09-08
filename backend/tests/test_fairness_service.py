"""The pre-filter must escalate biased reports and stay silent on clean ones.

Regression guard: an earlier regex anchored only the left word boundary, so
"management" matched "man" and every clean report escalated to the paid LLM
reviewer — the cost saving the pre-filter exists for never happened.
"""

import pytest
from services.fairness_service import (
    clean_fairness_result,
    needs_llm_fairness_review,
    sensitive_terms_found,
)


def _report(**overrides):
    base = {
        "executive_summary": "Solid backend engineer with strong ownership.",
        "technical_assessment": "Good grasp of Python and FastAPI. Has managed deployments.",
        "behavioral_assessment": "Clear communicator; mentoring juniors is a strength.",
        "consistency_analysis": "Test results align with interview feedback.",
        "justification": "Recommend moving to the next stage.",
        "domain_fit": "Strong fit for backend development roles.",
        "strengths": [{"text": "Python proficiency"}],
        "weaknesses": [{"text": "Limited Kubernetes exposure"}],
        "risks": [],
    }
    base.update(overrides)
    return base


def test_clean_report_does_not_escalate():
    report = _report()
    assert needs_llm_fairness_review(report) is False
    assert sensitive_terms_found(report) == []


@pytest.mark.parametrize(
    "word",
    ["management", "manager", "help", "held", "heavy", "hesitant", "mentoring",
     "hello", "agile", "ageless", "theory", "generational"],
)
def test_substrings_do_not_trigger(word):
    """Words merely *containing* a sensitive term must not escalate."""
    assert needs_llm_fairness_review(_report(justification=f"Strong {word} skills.")) is False


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("The candidate is a young man.", {"young", "man"}),
        ("She is recently married.", {"she", "married"}),
        ("Graduated from a top university, very prestigious.", {"top university", "prestigious"}),
        ("He is 45 years old.", {"he", "years old"}),
        ("Has a disability that may affect availability.", {"disability"}),
    ],
)
def test_real_sensitive_terms_escalate(phrase, expected):
    report = _report(executive_summary=phrase)
    assert needs_llm_fairness_review(report) is True
    assert expected.issubset(set(sensitive_terms_found(report)))


def test_sensitive_term_inside_cited_items_is_found():
    report = _report(strengths=[{"text": "Young and energetic"}])
    assert needs_llm_fairness_review(report) is True


def test_clean_result_shape():
    assert clean_fairness_result() == {"status": "ok", "flags": []}
