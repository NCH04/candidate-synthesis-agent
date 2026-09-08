"""The deterministic test-sheet parser: buckets and title handling."""

from pathlib import Path

import pytest
from services.test_parser_service import _bucket, _clean_title, parse_test_sheet_regex

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SHEET = """\
Technical Evaluation

1. Python — backend development
   Score: 4 / 5
   Notes: Solid.

2. Problem-solving under pressure
   Score: 3 / 5

3. Career goals alignment
   Score: 5 / 5

4. Communication: clarity of explanation
   Score: 4 / 5
"""


def test_hyphenated_title_is_not_truncated():
    """"Problem-solving under pressure" must stay whole.

    Cutting at the first hyphen produced "Problem", which matched no soft-skill
    keyword and was filed as a technical competency.
    """
    assert _clean_title("Problem-solving under pressure") == "Problem-solving under pressure"


@pytest.mark.parametrize("raw,expected", [
    ("Python — backend development", "Python"),
    ("Communication: clarity of explanation", "Communication"),
    ("Docker - containerization", "Docker"),
    ("CI/CD pipelines", "CI/CD pipelines"),
    ("Node.js", "Node.js"),
])
def test_titles_cut_only_on_real_separators(raw, expected):
    assert _clean_title(raw) == expected


@pytest.mark.parametrize("title,bucket", [
    ("Problem-solving under pressure", "soft"),
    ("Learning agility", "soft"),
    ("Communication", "soft"),
    ("Career goals alignment", "motivation"),
    ("Interest in backend development role", "motivation"),
    ("Company culture fit", "motivation"),
    ("Python", "technical"),
    ("Docker containerization", "technical"),
])
def test_bucketing(title, bucket):
    assert _bucket(title) == bucket


def test_parses_a_standard_sheet():
    result = parse_test_sheet_regex(SHEET)
    assert result is not None
    assert result["scores"] == {
        "technical.python": 4,
        "soft.problem_solving_under_pressure": 3,
        "motivation.career_goals_alignment": 5,
        "soft.communication": 4,
    }


def test_returns_none_on_an_unrecognised_layout():
    """Too few scored competencies → caller must fall back to the LLM parser."""
    assert parse_test_sheet_regex("Just some prose with no scores at all.") is None
    assert parse_test_sheet_regex("Python\nScore: 4/5\n") is None


def test_rescales_to_the_one_to_five_range():
    sheet = "A\nScore: 8/10\nB\nScore: 20/20\nC\nScore: 1/10\n"
    scores = parse_test_sheet_regex(sheet)["scores"]
    assert sorted(scores.values()) == [1, 4, 5]


@pytest.mark.parametrize("sheet_name", [
    "test_sheet_backend_engineer.txt",
    "test_sheet_fullstack_developer.txt",
])
def test_shipped_sample_sheets_cover_all_three_dimensions(sheet_name):
    """The bundled sheets must exercise technical, soft and motivation.

    They used to collapse almost entirely into `technical.*`, which then skewed
    the weighted score.
    """
    from services.fusion_service import covered_test_dimensions

    result = parse_test_sheet_regex((REPO_ROOT / sheet_name).read_text())
    assert result is not None
    assert covered_test_dimensions(result["scores"]) == {"technical", "soft", "motivation"}
