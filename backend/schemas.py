from typing import Any, Literal

from pydantic import BaseModel, Field, confloat, conint

DecisionType = Literal["Hire", "Consider", "No Hire"]
ConfidenceLevel = Literal["High", "Medium", "Low"]
ExperienceFit = Literal["poor", "fair", "good", "strong"]
MotivationSignal = Literal["low", "medium", "high"]
PsychologicalSignal = Literal["negative", "mixed", "positive", "positive and engaged"]
InterviewType = Literal["technical_interview", "hr_interview", "manager_interview", "assessment_review"]
CitationSource = Literal["cv", "test", "interview"]


class CandidateContext(BaseModel):
    candidate_id: str
    candidate_name: str | None = None


class JobContext(BaseModel):
    job_id: str
    job_title: str
    target_skills: list[str] = Field(default_factory=list)


class TestScoresInput(BaseModel):
    scores: dict[str, conint(ge=1, le=5)]


class InterviewInput(BaseModel):
    interview_type: InterviewType
    review_text: str = Field(..., min_length=10)


class FullPipelineRequest(BaseModel):
    candidate_context: CandidateContext
    job_context: JobContext
    test_results: TestScoresInput
    interview: InterviewInput


class CVProfileMatching(BaseModel):
    score: confloat(ge=0.0, le=100.0)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    experience_fit: str
    summary: str


class AggregatedTestScores(BaseModel):
    technical_score: confloat(ge=0.0, le=5.0)
    soft_skills_score: confloat(ge=0.0, le=5.0)
    motivation_score: confloat(ge=0.0, le=5.0)


class TestAssessment(BaseModel):
    raw_scores: dict[str, conint(ge=1, le=5)]
    aggregated_scores: AggregatedTestScores
    # Dimensions the sheet actually scored. A dimension absent from this list
    # reads 0.0 in `aggregated_scores` meaning "not evaluated", and is excluded
    # from every weighted average — see fusion_service.
    scored_dimensions: list[Literal["technical", "soft", "motivation"]] = Field(
        default_factory=list
    )
    summary: str


class ExtractedInterviewSignals(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    motivation_signal: MotivationSignal
    psychological_signal: PsychologicalSignal
    summary: str


class InterviewAssessment(BaseModel):
    interview_type: InterviewType
    review_text: str
    extracted_signals: ExtractedInterviewSignals
    summary: str


class FusionWeights(BaseModel):
    cv_profile_matching: confloat(ge=0.0, le=1.0) = 0.35
    test_assessment: confloat(ge=0.0, le=1.0) = 0.40
    interview_assessment: confloat(ge=0.0, le=1.0) = 0.25


class DimensionScores(BaseModel):
    technical_fit: confloat(ge=0.0, le=1.0)
    motivation_fit: confloat(ge=0.0, le=1.0)
    communication_fit: confloat(ge=0.0, le=1.0)
    overall_score: confloat(ge=0.0, le=1.0)


class FinalEvidence(BaseModel):
    top_strengths: list[str] = Field(default_factory=list)
    top_weaknesses: list[str] = Field(default_factory=list)
    top_risks: list[str] = Field(default_factory=list)


class FusionSummary(BaseModel):
    weights: FusionWeights
    dimension_scores: DimensionScores
    consistency_flags: list[str] = Field(default_factory=list)
    final_evidence: FinalEvidence


class CandidateAssessmentObject(BaseModel):
    candidate_context: CandidateContext
    job_context: JobContext
    cv_profile_matching: CVProfileMatching
    test_assessment: TestAssessment
    interview_assessment: InterviewAssessment
    fusion_summary: FusionSummary


# ---------------------------------------------------------------------------
# Synthesis report — every claim carries a citation back to source evidence
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    source: CitationSource
    extract: str


class CitedItem(BaseModel):
    text: str
    citation: Citation


class FairnessFlag(BaseModel):
    field: str
    issue: str
    suggestion: str


class FairnessReport(BaseModel):
    status: Literal["ok", "flagged"]
    flags: list[FairnessFlag] = Field(default_factory=list)


class CandidateSynthesisReport(BaseModel):
    executive_summary: str
    decision: DecisionType
    confidence_level: ConfidenceLevel
    overall_score: confloat(ge=0.0, le=1.0)
    strengths: list[CitedItem] = Field(default_factory=list)
    weaknesses: list[CitedItem] = Field(default_factory=list)
    risks: list[CitedItem] = Field(default_factory=list)
    technical_assessment: str
    behavioral_assessment: str
    consistency_analysis: str
    justification: str
    domain_fit: str
    fairness: FairnessReport | None = None


# ---------------------------------------------------------------------------
# Agent output contracts
#
# Each of these validates one Claude agent's JSON response. They are the
# guardrail against a hallucinated shape reaching the fusion layer or the UI:
# llm_service._json_chat validates against them and retries once on failure.
# ---------------------------------------------------------------------------

class CVExperience(BaseModel):
    title: str = ""
    context: str = ""
    duration: str = ""
    summary: str = ""


class CVEducation(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""


class CVProfile(BaseModel):
    """Output of the CV structure extractor agent."""
    full_name: str = ""
    skills: list[str] = Field(default_factory=list)
    experiences: list[CVExperience] = Field(default_factory=list)
    education: list[CVEducation] = Field(default_factory=list)
    summary: str = ""


class ProfileJobScore(BaseModel):
    """Output of the profile/job fit scorer agent."""
    score: confloat(ge=0.0, le=100.0)
    experience_fit: str = ""
    summary: str = ""


class TestSheetParseResult(BaseModel):
    """Output of the test-sheet parser agent (and of the regex parser)."""
    scores: dict[str, conint(ge=1, le=5)]
    target_skills: list[str] = Field(default_factory=list)


class CVParseResponse(BaseModel):
    """`POST /api/cv/parse` response."""
    full_name: str = ""
    skills: list[str] = Field(default_factory=list)
    experience_count: int = 0
    education_count: int = 0
    summary: str = ""


class AppConfigResponse(BaseModel):
    """`GET /api/config` response."""
    demo_mode: bool
    economy_mode: bool
    models: dict[str, str]


class JobsListResponse(BaseModel):
    jobs: list[dict[str, Any]] = Field(default_factory=list)


class AssessmentResponse(BaseModel):
    assessment: CandidateAssessmentObject


class PipelineSteps(BaseModel):
    cv_parsed: bool
    profile_scored: bool
    interview_extracted: bool
    fusion_completed: bool
    synthesis_generated: bool
    critic_refined: bool
    fairness_checked: bool


class FullPipelineResponse(BaseModel):
    pipeline_steps: PipelineSteps
    assessment: CandidateAssessmentObject
    synthesis_report: CandidateSynthesisReport
