import { FormValues, PipelineResult } from '../types'

const BASE = '/api'

export async function runFullPipeline(form: FormValues): Promise<PipelineResult> {
  if (!form.cvFile) throw new Error('CV file is required')

  const fd = new FormData()
  fd.append('file', form.cvFile)
  fd.append('candidate_id', form.candidateId || `cand_${Date.now()}`)
  fd.append('candidate_name', form.candidateName)
  fd.append('job_id', form.jobId)
  fd.append('job_title', form.jobTitle)
  fd.append('target_skills', form.targetSkills)
  fd.append('hrflow_board_key', form.boardKey)
  fd.append('test_results_json', form.testResultsJson)
  fd.append('interview_type', form.interviewType)
  fd.append('review_text', form.reviewText)
  fd.append('source_key', form.sourceKey)

  const res = await fetch(`${BASE}/candidate/full-pipeline`, {
    method: 'POST',
    body: fd,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Pipeline failed')
  }

  return res.json()
}
