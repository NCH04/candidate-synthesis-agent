# AI Candidate Synthesis Agent

## 1. Overview

This project is an AI-powered recruitment assistant that generates **standardized candidate syntheses** for shortlisted applicants.

The system consolidates three main evaluation sources:

1. **CV / profile matching**
2. **test results**
3. **interview feedback**

The goal is to transform fragmented recruitment signals into a **single structured recruitment summary** that is:
- clear,
- explainable,
- consistent across candidates,
- easy for recruiters to compare.

This project is designed as a **controlled AI pipeline**, not as a free-form chatbot.
The intelligence comes from:
- structured data processing,
- weighted multi-source fusion,
- two specialized AI reasoning steps.

---

## 2. Problem Statement

Recruitment evaluation is often fragmented across:
- resumes,
- technical tests,
- interview notes,
- recruiter impressions.

This creates several problems:
- inconsistent decision-making,
- subjective assessments,
- weak comparability across candidates,
- poor traceability of hiring recommendations.

Our solution is an AI agent pipeline that:
- standardizes all candidate inputs,
- extracts structured signals from raw human feedback,
- combines objective and qualitative evidence,
- generates a final hiring-oriented synthesis.

---

## 3. Objective

The objective of the system is to produce a **standardized candidate synthesis report** based on:

- **CV/profile matching analysis**
- **technical / structured test results**
- **interview feedback**
- **motivation and psychological signals extracted from interview text**

The final output must be a **single file / single report** that summarizes:
- technical fit,
- motivation,
- communication / behavioral signals,
- risks,
- final recommendation.

---

## 4. Core Inputs

The system relies on **three main inputs**.

### 4.1 CV / Profile Input

The CV is the candidate’s formal professional profile.

It is used to extract:
- declared skills,
- experience,
- education,
- role alignment,
- profile-job matching score.

This input is processed through **HrFlow parsing and profile/job scoring**.

---

### 4.2 Test Results Input

Test results are provided in **structured JSON format**.

This input represents measurable candidate performance.

Example:

```json
{
  "technical.python": 4,
  "technical.sql": 3,
  "technical.system_design": 2,
  "soft.communication": 4,
  "motivation.role_interest": 5
}
This format is chosen because it is:

machine-readable,
easy to validate,
easy to normalize,
easy to aggregate.
4.3 Interview Feedback Input

Interview feedback is provided as unstructured natural language text.

Example:

"Strong in backend and APIs, but lacks depth in system design. Good communication and strong motivation."

This input captures information that numeric scores alone cannot capture:

perceived strengths,
perceived weaknesses,
motivation,
attitude,
communication,
psychological or behavioral signals,
recruiter concerns.
5. Why These 3 Inputs

These three inputs are complementary:

CV/profile matching tells us what the candidate looks like on paper
test results tell us what the candidate demonstrated in evaluation
interview feedback tells us how the candidate was perceived and what qualitative signals emerged

This combination allows the system to avoid:

overvaluing CVs,
relying only on recruiter intuition,
making decisions from incomplete evidence.
6. Global Processing Pipeline

The system follows a controlled, multi-stage pipeline.
Recruiter Inputs
   ├── CV file
   ├── Test results JSON
   └── Interview feedback text

CV → HrFlow Parsing → Structured Profile → HrFlow Profile/Job Scoring

Test JSON → Validation → Normalization → Aggregation

Interview Text → LLM Extraction → Structured Signals

All Processed Data → Fusion Layer → Candidate Assessment Object → Final LLM Synthesis → Final Report

7. Detailed Input Processing Pipeline

This section explains the purpose of each input stage and how the data is transformed.

7.1 CV Processing Pipeline
Goal

The goal of the CV pipeline is to transform a raw uploaded resume into:

a structured candidate profile,
a job matching score,
an interpretable summary of profile alignment.
Steps
Step 1 — CV Upload

The recruiter uploads a CV file from the frontend.

Accepted formats can include:

PDF
DOCX
plain text (optional)
Step 2 — CV Parsing via HrFlow

The backend sends the uploaded CV to HrFlow parsing services.

This parsing step transforms the raw document into structured profile information such as:

name,
experience,
education,
skills,
role-related signals.
Step 3 — Profile Retrieval

Once parsed, the backend retrieves the normalized profile data.

Step 4 — Profile/Job Scoring

The backend then scores the parsed candidate profile against the target job.

This creates a structured objective baseline for the candidate.

CV Processing Output

Example:

{
  "score": 78,
  "matched_skills": ["Python", "SQL", "FastAPI"],
  "missing_skills": ["Docker"],
  "experience_fit": "good",
  "summary": "Candidate shows strong alignment with backend requirements with minor gaps."
}
Why this matters

This stage provides:

an objective role alignment score,
evidence of skills matching,
a baseline before subjective interpretation is introduced.
7.2 Test Results Processing Pipeline
Goal

The goal of this stage is to transform structured score inputs into stable evaluation dimensions.

Input Format
{
  "technical.python": 4,
  "technical.sql": 3,
  "technical.system_design": 2,
  "soft.communication": 4,
  "motivation.role_interest": 5
}
Processing Steps
Step 1 — Schema Validation

The backend checks:

that the JSON is valid,
that keys follow the expected schema,
that scores are within the accepted range.

Recommended score scale:

1 = weak
2 = insufficient
3 = acceptable
4 = good
5 = excellent
Step 2 — Normalization

Scores are normalized to a consistent internal scale.

Example:

raw 1–5 scale remains interpretable,
later converted to normalized values for fusion.
Step 3 — Aggregation by Dimension

Individual competency scores are grouped into broader categories:

technical fit,
soft skills,
motivation.
Test Processing Output
{
  "technical_score": 3.0,
  "soft_skills_score": 4.0,
  "motivation_score": 5.0,
  "summary": "Strong in Python and communication, weaker in system design."
} 
Why this matters

This stage converts raw evaluation scores into:

stable dimensions,
comparable candidate metrics,
fusion-ready evidence.
7.3 Interview Feedback Processing Pipeline
Goal

The goal of this stage is to transform recruiter-written free text into structured hiring signals.

Why LLM parsing is needed

Interview notes are often:

subjective,
unstructured,
inconsistent in style,
difficult to compare directly across candidates.

A recruiter may write:

a long paragraph,
short bullet notes,
vague remarks,
mixed positive/negative comments.

The system needs to convert that into structured evidence.

Input Example

"Strong in backend and APIs, but lacks depth in system design. Good communication and strong motivation."

Step 1 — LLM Extraction

A dedicated AI reasoning step analyzes the raw interview review text and extracts:

strengths,
weaknesses,
risks,
motivation signal,
psychological/behavioral signal,
a short structured summary.
Interview Parsing Output
{
  "strengths": ["backend development", "Python", "communication", "motivation"],
  "weaknesses": ["system design", "architecture depth"],
  "risks": ["limited scalability experience"],
  "motivation_signal": "high",
  "psychological_signal": "positive and engaged",
  "summary": "Interview confirms backend strength, strong engagement, and a weakness in architecture depth."
}
Why this matters

This stage captures qualitative information that numbers cannot fully represent:

enthusiasm,
confidence,
recruiter trust,
behavioral fit,
risk concerns.
8. Data Fusion Layer
Goal

The goal of the fusion layer is to combine the three processed inputs into a single coherent candidate assessment package.

The fusion layer is the most important non-LLM part of the system.

It is responsible for:

combining quantitative and qualitative evidence,
computing weighted scores,
detecting reinforcing signals,
detecting contradictions,
preparing a final structured object for the synthesis model.
8.1 Weighting Strategy

For the MVP, the fusion uses fixed weights:

CV / Profile Matching: 35%
Test Results: 40%
Interview Feedback: 25%
Why this weighting is reasonable
CV/profile matching is useful, but should not dominate the whole decision
test results are given the highest weight because they reflect demonstrated ability
interview feedback remains important but should not override objective evidence
8.2 Fusion Logic

The fusion layer performs three major operations.

A. Score Combination

The backend computes normalized scores and produces dimension-level outputs such as:

technical fit,
communication fit,
motivation fit,
overall score.
B. Signal Consolidation

The backend merges:

strengths,
weaknesses,
risks,
across all sources.
C. Consistency Analysis

The backend detects:

reinforcing evidence,
contradictions between sources,
repeated weaknesses,
repeated strengths.

Examples:

CV and interview both confirm backend strength
test and interview both confirm system design weakness
CV claims architecture experience but test/interview do not confirm it
9. Candidate Assessment Object

The final output of the fusion layer is a Candidate Assessment Object.

This is the structured object sent to the final synthesis agent.

It is not raw input.
It is not a dump of every field.
It is a cleaned, summarized, weighted, structured evaluation package.

Final Fusion Object
{
  "candidate_context": {
    "candidate_id": "cand_001",
    "candidate_name": "John Doe"
  },
  "job_context": {
    "job_id": "job_backend_01",
    "job_title": "Backend Engineer",
    "target_skills": ["Python", "SQL", "FastAPI", "Docker"]
  },
  "cv_profile_matching": {
    "score": 78,
    "matched_skills": ["Python", "SQL", "FastAPI"],
    "missing_skills": ["Docker"],
    "experience_fit": "good",
    "summary": "Candidate shows strong alignment with backend requirements with minor gaps."
  },
  "test_assessment": {
    "raw_scores": {
      "technical.python": 4,
      "technical.sql": 3,
      "technical.system_design": 2,
      "soft.communication": 4,
      "motivation.role_interest": 5
    },
    "aggregated_scores": {
      "technical_score": 3.0,
      "soft_skills_score": 4.0,
      "motivation_score": 5.0
    },
    "summary": "Strong in Python and communication, weaker in system design."
  },
  "interview_assessment": {
    "interview_type": "technical_interview",
    "review_text": "Strong backend profile but lacks depth in architecture.",
    "extracted_signals": {
      "strengths": ["backend", "Python", "communication", "motivation"],
      "weaknesses": ["system design"],
      "risks": ["limited architecture depth"],
      "motivation_signal": "high",
      "psychological_signal": "positive"
    },
    "summary": "Interview confirms backend strength but highlights architectural gaps."
  },
  "fusion_summary": {
    "weights": {
      "cv_profile_matching": 0.35,
      "test_assessment": 0.40,
      "interview_assessment": 0.25
    },
    "dimension_scores": {
      "technical_fit": 0.67,
      "motivation_fit": 0.95,
      "communication_fit": 0.80,
      "overall_score": 0.77
    },
    "consistency_flags": [
      "Backend strength confirmed across CV and interview",
      "System design weakness confirmed across test and interview"
    ],
    "final_evidence": {
      "top_strengths": ["Python", "backend APIs", "communication"],
      "top_weaknesses": ["system design"],
      "top_risks": ["limited scalability experience"]
    }
  }
}
10. AI Agent Design

This project uses two specialized pseudo-agents, implemented as two controlled LLM reasoning steps.

This is intentional.

We do not want an uncontrolled autonomous agent.
We want a deterministic pipeline with clear responsibilities.

10.1 Agent 1 — Interview Parsing Agent
Role

Transform raw interview review text into structured recruitment signals.

Input
raw interview text
Output
strengths
weaknesses
risks
motivation signal
psychological signal
summary
Why it exists

This agent standardizes recruiter text and makes it machine-readable.

10.2 Agent 2 — Final Synthesis Agent
Role

Generate the final standardized candidate synthesis report from the Candidate Assessment Object.

Input
fully structured fusion object
Output
executive summary
recommendation
strengths
weaknesses
risks
technical assessment
behavioral assessment
consistency analysis
final justification
Why it exists

This agent transforms structured evidence into a readable, recruiter-facing final report.

11. Final Output Format

The final output of the system is a standardized candidate synthesis report.

It must always follow the same structure to ensure comparability.

Human-readable structure
Executive Summary
Overall Recommendation
Key Strengths
Key Weaknesses
Risk Factors
Technical Assessment
Behavioral & Motivation Assessment
Consistency Analysis
Final Justification
Example Human-readable Output
Executive Summary

Strong backend-oriented candidate with good Python skills and high motivation. However, the candidate shows weaker system design depth and limited architecture exposure. Suitable for a backend role with technical mentorship.

Overall Recommendation
Decision: Consider
Confidence Level: Medium
Overall Score: 0.77
Key Strengths
Strong Python skills
Good backend API understanding
High motivation
Clear communication
Key Weaknesses
Weak system design depth
Limited architecture exposure
Risk Factors
May require support for scalability and system design topics
Technical Assessment

The candidate demonstrates solid backend capability and relevant technical alignment with the job. However, both test results and interview feedback reveal a recurring weakness in architecture-level reasoning.

Behavioral & Motivation Assessment

The candidate appears engaged, communicates clearly, and shows strong interest in the role. Motivation is consistently high across evaluation signals.

Consistency Analysis

Backend strengths are confirmed across CV and interview feedback. System design weakness is confirmed across test results and interview assessment. No major contradiction is detected.

Final Justification

The candidate is a strong backend-oriented profile with clear motivation and good communication. Because system design weaknesses appear repeatedly, the recommendation is "Consider" rather than immediate "Hire".

JSON Output Format
{
  "executive_summary": "Strong backend-oriented candidate with good Python skills and high motivation, but weaker system design depth.",
  "decision": "Consider",
  "confidence_level": "Medium",
  "overall_score": 0.77,
  "strengths": [
    "Strong Python skills",
    "Good backend API understanding",
    "High motivation",
    "Clear communication"
  ],
  "weaknesses": [
    "Weak system design depth",
    "Limited architecture exposure"
  ],
  "risks": [
    "May require mentorship on scalability topics"
  ],
  "technical_assessment": "The candidate is well aligned with backend development needs but has a weaker profile in distributed architecture and system design.",
  "behavioral_assessment": "The candidate communicates clearly, appears engaged, and shows a strong willingness to learn.",
  "consistency_analysis": "Backend strengths are confirmed across CV and interview. System design weakness is confirmed across test and interview.",
  "justification": "The candidate is a solid backend profile with strong motivation, but the repeated weakness in system design suggests a 'Consider' recommendation rather than a direct 'Hire'."
}
12. Frontend Specification

The frontend is designed for recruiters or HR users.

Its role is to:

collect structured inputs,
send them to the backend,
visualize processing states,
display the final report.
12.1 Frontend Technical Stack
React
TypeScript
Vite
Tailwind CSS
shadcn/ui (optional but recommended)
React Hook Form
Zod (optional for validation)
12.2 Frontend Pages / Views
A. Input Page

This page allows the recruiter to submit:

CV file upload
target job title / target job ID
candidate name / candidate ID
test results JSON
interview type
interview feedback text
B. Processing View

This view shows pipeline progression:

CV parsed
profile matched to job
interview signals extracted
fusion object created
final synthesis generated
C. Results Page

This page displays:

executive summary
recommendation
strengths
weaknesses
risks
technical assessment
behavioral assessment
consistency analysis
final justification
12.3 Frontend UX Goal

The frontend should feel like a guided recruiter workflow, not like a generic chatbot.

The ideal experience is:

fill inputs,
click generate,
see processing steps,
receive final synthesis report.
13. Backend Specification

The backend orchestrates the full pipeline.

It is responsible for:

receiving recruiter inputs,
calling HrFlow for CV/profile processing,
validating test JSON,
calling LLM for interview parsing,
building the fusion object,
calling LLM for final synthesis generation,
returning the final standardized report.
13.1 Backend Technical Stack
Python 3.11+
FastAPI
Pydantic
httpx
python-multipart
uvicorn

Optional:

SQLite for persistence
or in-memory state for the MVP demo
13.2 Backend Architecture
Frontend
   ↓
FastAPI Backend
   ├── CV Processing Service
   ├── Test Validation & Aggregation Service
   ├── Interview Extraction Service
   ├── Fusion Service
   └── Final Synthesis Service
        ↓
External APIs
   ├── HrFlow API
   └── OpenAI API
14. API Endpoints

For the MVP, the backend should expose the following routes.

14.1 Parse CV
POST /api/cv/parse

Purpose:

receive CV file,
forward it to HrFlow,
return normalized CV/profile information.
14.2 Extract Interview Signals
POST /api/candidate/interview/extract

Purpose:

send interview feedback text to the interview parsing agent,
return structured interview signals.
14.3 Build Candidate Assessment
POST /api/candidate/assessment/build

Purpose:

combine CV/profile matching,
test results,
structured interview signals,
build the final Candidate Assessment Object.
14.4 Generate Candidate Synthesis
POST /api/candidate/synthesis/generate

Purpose:

send the fused assessment object to the final synthesis agent,
return the standardized report.
14.5 Full Pipeline Endpoint
POST /api/candidate/full-pipeline

Purpose:
Single demo endpoint that:

parses the CV,
scores profile/job fit,
validates and aggregates test results,
extracts interview signals,
builds the fusion object,
generates the final report.

This is the best route for the hackathon demo.

15. Pydantic Schemas
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
    job_id: str
    job_title: str
    target_skills: List[str] = Field(default_factory=list)


class TestScoresInput(BaseModel):
    scores: Dict[str, conint(ge=1, le=5)]


class InterviewInput(BaseModel):
    interview_type: InterviewType
    review_text: str = Field(..., min_length=10)


class CandidateProcessingRequest(BaseModel):
    candidate_context: CandidateContext
    job_context: JobContext
    test_results: TestScoresInput
    interview: InterviewInput
    hrflow_profile_id: Optional[str] = None


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
16. FastAPI Endpoint Skeleton
from fastapi import FastAPI, UploadFile, File
from typing import Any, Dict

app = FastAPI(title="AI Candidate Synthesis Agent")


@app.post("/api/cv/parse")
async def parse_cv(file: UploadFile = File(...)) -> Dict[str, Any]:
    return {"message": "CV parsed successfully"}


@app.post("/api/candidate/interview/extract")
async def extract_interview_signals(payload: dict) -> Dict[str, Any]:
    return {"message": "Interview signals extracted"}


@app.post("/api/candidate/assessment/build")
async def build_candidate_assessment(payload: dict) -> Dict[str, Any]:
    return {"message": "Candidate assessment built"}


@app.post("/api/candidate/synthesis/generate")
async def generate_candidate_synthesis(payload: dict) -> Dict[str, Any]:
    return {"message": "Candidate synthesis generated"}


@app.post("/api/candidate/full-pipeline")
async def full_pipeline(payload: dict) -> Dict[str, Any]:
    return {"message": "Full pipeline executed"}
17. LLM Prompts
17.1 Interview Parsing Agent Prompt
You are an AI recruitment signal extractor.

Your task is to analyze unstructured interview feedback and convert it into structured recruitment signals.

You must extract:
- strengths
- weaknesses
- risks
- motivation_signal
- psychological_signal
- summary

Rules:
- Use only the provided text
- Do not invent information
- Keep items concise
- motivation_signal must be one of: low, medium, high
- psychological_signal must be one of: negative, mixed, positive, positive and engaged
- Return valid JSON only

Input:
{{review_text}}

Expected JSON:
{
  "strengths": ["..."],
  "weaknesses": ["..."],
  "risks": ["..."],
  "motivation_signal": "medium",
  "psychological_signal": "positive",
  "summary": "..."
}
17.2 Final Synthesis Agent Prompt
You are an AI recruitment analyst.

You receive a fully processed candidate assessment object.
Your task is to generate a standardized candidate synthesis report.

Rules:
- Use only the provided structured evidence
- Do not invent facts
- Clearly distinguish strengths, weaknesses, and risks
- The decision must be one of: Hire, Consider, No Hire
- The confidence_level must be one of: High, Medium, Low
- Return valid JSON only

Input:
{{candidate_assessment_object}}

Expected JSON format:
{
  "executive_summary": "...",
  "decision": "Consider",
  "confidence_level": "Medium",
  "overall_score": 0.77,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "risks": ["..."],
  "technical_assessment": "...",
  "behavioral_assessment": "...",
  "consistency_analysis": "...",
  "justification": "..."
}
18. Demo Flow

The demo should present the system as a guided recruiter workflow.

Demo Steps
Recruiter uploads a CV
Recruiter enters or selects the target job
Recruiter pastes structured test results JSON
Recruiter pastes interview feedback text
Backend parses CV and scores profile/job fit
Backend calls the interview parsing agent
Backend validates test results and aggregates scores
Backend fuses all processed data into a Candidate Assessment Object
Backend calls the final synthesis agent
Frontend displays the final standardized candidate report
Demo UX Recommendation

Show a pipeline timeline such as:

CV parsed
Profile scored
Interview extracted
Fusion completed
Synthesis generated

This makes the “agent” feel visible and intelligent during the demo.

19. Key Engineering Principles
Controlled AI

The system does not let the model invent structure.
All important structure is built before the final synthesis call.

Explainability

Every recommendation must be justified by evidence.

Modularity

Each stage can be tested independently:

CV scoring
test processing
interview extraction
fusion
synthesis
Standardization

All candidates are evaluated under the same schema and output format.

20. MVP Scope

The MVP includes:

CV parsing and matching
JSON test processing
interview feedback parsing with LLM
weighted fusion
final synthesis generation
recruiter-facing UI
21. Future Improvements

Potential extensions:

multiple interview aggregation
candidate comparison dashboard
bias flags
recruiter feedback loop
export to PDF
job-specific dynamic weighting
historical evaluation persistence
recruiter editable final report
22. Conclusion

This project is not a generic chatbot.

It is a structured AI recruitment pipeline that:

ingests multiple candidate evaluation sources,
converts them into normalized structured evidence,
fuses them through weighted logic,
generates a final explainable hiring-oriented synthesis.

The system is specifically designed for:

consistency,
transparency,
recruiter usability,
hackathon demo clarity,
direct implementation by an AI coding assistant.