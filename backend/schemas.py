from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, conint, confloat

DecisionType = Literal["Hire", "Consider", "No Hire"]
ConfidenceLevel = Literal["High", "Medium", "Low"]
ExperienceFit = Literal["poor", "fair", "good", "strong"]
MotivationSignal = Literal["low", "medium", "high"]
PsychologicalSignal = Literal["negative", "mixed", "positive", "positive and engaged"]
InterviewType = Literal["technical_interview", "hr_interview", "manager_interview", "assessment_review"]


class CandidateContext(BaseModel):
    candidate_id: str
    candidate_name: Optional[str] = None


class JobContext(BaseModel):
    job_id: str  # HrFlow job_key or job_reference
    job_title: str
    target_skills: List[str] = Field(default_factory=list)


class TestScoresInput(BaseModel):
    scores: Dict[str, conint(ge=1, le=5)]


class InterviewInput(BaseModel):
    interview_type: InterviewType
    review_text: str = Field(..., min_length=10)


class FullPipelineRequest(BaseModel):
    candidate_context: CandidateContext
    job_context: JobContext
    hrflow_board_key: str = Field(..., description="HrFlow board key where the job is stored")
    test_results: TestScoresInput
    interview: InterviewInput


class CVProfileMatching(BaseModel):
    score: confloat(ge=0.0, le=100.0)
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    experience_fit: ExperienceFit
    summary: str


class AggregatedTestScores(BaseModel):
    technical_score: confloat(ge=0.0, le=5.0)
    soft_skills_score: confloat(ge=0.0, le=5.0)
    motivation_score: confloat(ge=0.0, le=5.0)


class TestAssessment(BaseModel):
    raw_scores: Dict[str, conint(ge=1, le=5)]
    aggregated_scores: AggregatedTestScores
    summary: str


class ExtractedInterviewSignals(BaseModel):
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
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
    top_strengths: List[str] = Field(default_factory=list)
    top_weaknesses: List[str] = Field(default_factory=list)
    top_risks: List[str] = Field(default_factory=list)


class FusionSummary(BaseModel):
    weights: FusionWeights
    dimension_scores: DimensionScores
    consistency_flags: List[str] = Field(default_factory=list)
    final_evidence: FinalEvidence


class CandidateAssessmentObject(BaseModel):
    candidate_context: CandidateContext
    job_context: JobContext
    cv_profile_matching: CVProfileMatching
    test_assessment: TestAssessment
    interview_assessment: InterviewAssessment
    fusion_summary: FusionSummary


class CandidateSynthesisReport(BaseModel):
    executive_summary: str
    decision: DecisionType
    confidence_level: ConfidenceLevel
    overall_score: confloat(ge=0.0, le=1.0)
    strengths: List[str]
    weaknesses: List[str]
    risks: List[str]
    technical_assessment: str
    behavioral_assessment: str
    consistency_analysis: str
    justification: str
    domain_fit: str
