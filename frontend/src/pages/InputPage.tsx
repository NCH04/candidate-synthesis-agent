import { useState, useRef, DragEvent, ChangeEvent } from 'react'
import { FormValues, InterviewType } from '../types'

const DEFAULT_TEST_JSON = JSON.stringify(
  {
    'technical.python': 4,
    'technical.sql': 3,
    'technical.system_design': 2,
    'soft.communication': 4,
    'motivation.role_interest': 5,
  },
  null,
  2,
)

const INTERVIEW_TYPES: { value: InterviewType; label: string }[] = [
  { value: 'technical_interview', label: 'Technical Interview' },
  { value: 'hr_interview', label: 'HR Interview' },
  { value: 'manager_interview', label: 'Manager Interview' },
  { value: 'assessment_review', label: 'Assessment Review' },
]

interface Props {
  onSubmit: (form: FormValues) => void
}

export default function InputPage({ onSubmit }: Props) {
  const [form, setForm] = useState<FormValues>({
    candidateName: '',
    candidateId: '',
    jobTitle: '',
    jobId: '',
    boardKey: '',
    sourceKey: '',
    targetSkills: '',
    cvFile: null,
    testResultsJson: DEFAULT_TEST_JSON,
    interviewType: 'technical_interview',
    reviewText: '',
  })
  const [dragging, setDragging] = useState(false)
  const [jsonError, setJsonError] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function set(key: keyof FormValues, value: string | File | null) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  function handleFileAccept(file: File) {
    set('cvFile', file)
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFileAccept(file)
  }

  function handleJsonChange(val: string) {
    set('testResultsJson', val)
    try {
      JSON.parse(val)
      setJsonError(null)
    } catch {
      setJsonError('Invalid JSON')
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onSubmit(form)
  }

  const canSubmit =
    form.cvFile !== null &&
    form.jobTitle.trim() !== '' &&
    form.testResultsJson.trim() !== '' &&
    form.reviewText.trim() !== '' &&
    jsonError === null

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Left column */}
        <div className="space-y-6">

          {/* Candidate */}
          <div className="card">
            <p className="section-title">Candidate</p>
            <div className="space-y-4">
              <div>
                <label className="label">Full name</label>
                <input className="input-field" placeholder="John Doe"
                  value={form.candidateName} onChange={e => set('candidateName', e.target.value)} />
              </div>
              <div>
                <label className="label">Candidate ID</label>
                <input className="input-field" placeholder="cand_001 (auto-generated if empty)"
                  value={form.candidateId} onChange={e => set('candidateId', e.target.value)} />
              </div>
            </div>
          </div>

          {/* Job */}
          <div className="card">
            <p className="section-title">Target job</p>
            <div className="space-y-4">
              <div>
                <label className="label">Job title <span className="text-red-400">*</span></label>
                <input className="input-field" placeholder="Backend Engineer" required
                  value={form.jobTitle} onChange={e => set('jobTitle', e.target.value)} />
              </div>
              <div>
                <label className="label">Target skills
                  <span className="ml-1 text-xs font-normal text-slate-400">(comma-separated)</span>
                </label>
                <input className="input-field" placeholder="Python, SQL, FastAPI, Docker"
                  value={form.targetSkills} onChange={e => set('targetSkills', e.target.value)} />
              </div>
            </div>
          </div>

          {/* CV Upload */}
          <div className="card">
            <p className="section-title">Resume / CV <span className="text-red-400">*</span></p>
            <div
              className={`relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed
                          px-6 py-8 text-center cursor-pointer transition-colors
                          ${dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 hover:border-brand-400 hover:bg-slate-50'}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input ref={fileInputRef} type="file" className="hidden"
                accept=".pdf,.doc,.docx,.txt"
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  const f = e.target.files?.[0]
                  if (f) handleFileAccept(f)
                }} />
              {form.cvFile ? (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-brand-100 flex items-center justify-center">
                    <svg className="w-5 h-5 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0119 9.414V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium text-slate-700">{form.cvFile.name}</p>
                    <p className="text-xs text-slate-400">{(form.cvFile.size / 1024).toFixed(0)} KB — click to change</p>
                  </div>
                </div>
              ) : (
                <>
                  <svg className="w-8 h-8 text-slate-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-sm font-medium text-slate-600">Drop your CV here or click to browse</p>
                  <p className="text-xs text-slate-400 mt-1">PDF, DOCX, DOC — max 10 MB</p>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">

          {/* Test results */}
          <div className="card">
            <div className="flex items-start justify-between mb-3">
              <p className="section-title mb-0">Test results <span className="text-red-400">*</span></p>
              <span className="text-xs text-slate-400">Keys: category.skill, scores 1–5</span>
            </div>
            <textarea
              className={`input-field font-mono text-xs h-40 resize-none ${jsonError ? 'border-red-400 focus:border-red-400 focus:ring-red-300/20' : ''}`}
              value={form.testResultsJson}
              onChange={e => handleJsonChange(e.target.value)}
              spellCheck={false}
            />
            {jsonError && <p className="mt-1 text-xs text-red-500">{jsonError}</p>}
          </div>

          {/* Interview */}
          <div className="card">
            <p className="section-title">Interview feedback <span className="text-red-400">*</span></p>
            <div className="space-y-4">
              <div>
                <label className="label">Interview type</label>
                <select className="input-field"
                  value={form.interviewType}
                  onChange={e => set('interviewType', e.target.value as InterviewType)}>
                  {INTERVIEW_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Recruiter notes</label>
                <textarea
                  className="input-field h-32 resize-none"
                  placeholder="Strong in backend and APIs, but lacks depth in system design. Good communication and strong motivation."
                  value={form.reviewText}
                  onChange={e => set('reviewText', e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced / HrFlow config */}
      <div className="card">
        <button type="button"
          className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700 transition-colors w-full"
          onClick={() => setShowAdvanced(v => !v)}>
          <svg className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          HrFlow configuration
          <span className="ml-auto text-xs font-normal text-slate-400">
            Optional — required for live HrFlow scoring
          </span>
        </button>
        {showAdvanced && (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="label">Source key</label>
              <input className="input-field" placeholder="src_xxxxxxxx"
                value={form.sourceKey} onChange={e => set('sourceKey', e.target.value)} />
              <p className="text-xs text-slate-400 mt-1">Where parsed profiles are stored</p>
            </div>
            <div>
              <label className="label">Board key</label>
              <input className="input-field" placeholder="board_xxxxxxxx"
                value={form.boardKey} onChange={e => set('boardKey', e.target.value)} />
              <p className="text-xs text-slate-400 mt-1">HrFlow board containing the job</p>
            </div>
            <div>
              <label className="label">Job key</label>
              <input className="input-field" placeholder="job_xxxxxxxx"
                value={form.jobId} onChange={e => set('jobId', e.target.value)} />
              <p className="text-xs text-slate-400 mt-1">HrFlow job reference for scoring</p>
            </div>
          </div>
        )}
      </div>

      {/* Submit */}
      <div className="flex justify-end">
        <button type="submit" className="btn-primary" disabled={!canSubmit}>
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Generate Synthesis
        </button>
      </div>
    </form>
  )
}
