import { CandidateAssessment, FormValues, PipelineResult } from '../types'

const BASE = '/api'

function toFormData(form: FormValues): FormData {
  if (!form.cvFile) throw new Error('CV file is required')
  const fd = new FormData()
  fd.append('file', form.cvFile)
  fd.append('candidate_id', form.candidateId || `cand_${Date.now()}`)
  fd.append('candidate_name', form.candidateName)
  fd.append('job_id', form.jobId)
  fd.append('job_title', form.jobTitle)
  fd.append('target_skills', form.targetSkills)
  fd.append('test_results_json', form.testResultsJson)
  fd.append('interview_type', form.interviewType)
  fd.append('review_text', form.reviewText)
  return fd
}

export async function runFullPipeline(form: FormValues): Promise<PipelineResult> {
  const res = await fetch(`${BASE}/candidate/full-pipeline`, { method: 'POST', body: toFormData(form) })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Pipeline failed')
  }
  return res.json()
}

export async function preparePipeline(form: FormValues): Promise<CandidateAssessment> {
  const res = await fetch(`${BASE}/candidate/pipeline/prepare`, { method: 'POST', body: toFormData(form) })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Pipeline prepare failed')
  }
  const data = await res.json()
  return data.assessment as CandidateAssessment
}

/**
 * Streaming variant — yields the synthesis draft token by token (SSE),
 * then emits one final 'final' event with the refined + fairness-checked report.
 */
export async function streamSynthesis(
  assessmentObject: unknown,
  onDelta: (text: string) => void,
  onFinal: (report: unknown) => void,
  onError?: (err: string) => void,
): Promise<void> {
  const res = await fetch(`${BASE}/candidate/synthesis/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(assessmentObject),
  })
  if (!res.ok || !res.body) {
    onError?.(`Stream failed: ${res.status}`)
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })

    // SSE messages are separated by blank lines
    const parts = buf.split('\n\n')
    buf = parts.pop() ?? ''

    for (const raw of parts) {
      const lines = raw.split('\n')
      let event = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) event = line.slice(7).trim()
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (!data) continue

      try {
        const payload = JSON.parse(data)
        if (event === 'delta') onDelta(payload.text ?? '')
        else if (event === 'final') onFinal(payload)
        else if (event === 'error') onError?.(payload.message ?? 'unknown error')
      } catch {
        // ignore malformed chunk
      }
    }
  }
}
