export type DecisionType = 'Hire' | 'Consider' | 'No Hire'
export type ConfidenceLevel = 'High' | 'Medium' | 'Low'
export type InterviewType =
  | 'technical_interview'
  | 'hr_interview'
  | 'manager_interview'
  | 'assessment_review'

export interface CandidateContext {
  candidate_id: string
  candidate_name: string
}

export interface JobContext {
  job_id: string
  job_title: string
  target_skills: string[]
}

export interface CVProfileMatching {
  score: number
  matched_skills: string[]
  missing_skills: string[]
  experience_fit: string
  summary: string
}

export interface AggregatedTestScores {
  technical_score: number
  soft_skills_score: number
  motivation_score: number
}

export interface TestAssessment {
  raw_scores: Record<string, number>
  aggregated_scores: AggregatedTestScores
  summary: string
}

export interface ExtractedInterviewSignals {
  strengths: string[]
  weaknesses: string[]
  risks: string[]
  motivation_signal: string
  psychological_signal: string
  summary: string
}

export interface InterviewAssessment {
  interview_type: string
  review_text: string
  extracted_signals: ExtractedInterviewSignals
  summary: string
}

export interface DimensionScores {
  technical_fit: number
  motivation_fit: number
  communication_fit: number
  overall_score: number
}

export interface FusionSummary {
  weights: { cv_profile_matching: number; test_assessment: number; interview_assessment: number }
  dimension_scores: DimensionScores
  consistency_flags: string[]
  final_evidence: {
    top_strengths: string[]
    top_weaknesses: string[]
    top_risks: string[]
  }
}

export interface CandidateAssessment {
  candidate_context: CandidateContext
  job_context: JobContext
  cv_profile_matching: CVProfileMatching
  test_assessment: TestAssessment
  interview_assessment: InterviewAssessment
  fusion_summary: FusionSummary
}

export interface SynthesisReport {
  executive_summary: string
  decision: DecisionType
  confidence_level: ConfidenceLevel
  overall_score: number
  strengths: string[]
  weaknesses: string[]
  risks: string[]
  technical_assessment: string
  behavioral_assessment: string
  consistency_analysis: string
  justification: string
  domain_fit: string
}

export interface PipelineResult {
  pipeline_steps: Record<string, boolean>
  assessment: CandidateAssessment
  synthesis_report: SynthesisReport
}

export interface JobOption {
  key: string
  title: string
  skills: string[]
  summary: string
}

export interface FormValues {
  candidateName: string
  candidateId: string
  jobTitle: string
  jobId: string
  boardKey: string
  sourceKey: string
  targetSkills: string        // auto-filled from test parse
  cvFile: File | null
  testFile: File | null       // replaces manual JSON — parsed automatically
  testResultsJson: string     // auto-filled after test parse
  interviewType: InterviewType
  reviewText: string
}
