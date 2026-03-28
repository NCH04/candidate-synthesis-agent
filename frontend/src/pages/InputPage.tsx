import { useState, useRef, useEffect, RefObject, DragEvent, ChangeEvent } from 'react'
import { FormValues, InterviewType, JobOption } from '../types'

const INTERVIEW_TYPES: { value: InterviewType; label: string }[] = [
  { value: 'technical_interview', label: 'Technical Interview' },
  { value: 'hr_interview', label: 'HR Interview' },
  { value: 'manager_interview', label: 'Manager Interview' },
  { value: 'assessment_review', label: 'Assessment Review' },
]

interface ParsedTest {
  scores: Record<string, number>
  target_skills: string[]
}

interface Props {
  onSubmit: (form: FormValues) => void
  jobs: JobOption[]
}

export default function InputPage({ onSubmit, jobs }: Props) {
  const [form, setForm] = useState<FormValues>({
    candidateName: '',
    candidateId: '',
    jobTitle: '',
    jobId: '',
    boardKey: '',
    sourceKey: '',
    targetSkills: '',
    cvFile: null,
    testFile: null,
    testResultsJson: '',
    interviewType: 'technical_interview',
    reviewText: '',
  })
  const [cvDragging, setCvDragging] = useState(false)
  const [cvParsing, setCvParsing] = useState(false)
  const [cvParsed, setCvParsed] = useState(false)
  const [cvParseError, setCvParseError] = useState<string | null>(null)
  const [testDragging, setTestDragging] = useState(false)
  const [testParsed, setTestParsed] = useState<ParsedTest | null>(null)
  const [testParsing, setTestParsing] = useState(false)
  const [testParseError, setTestParseError] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [jobQuery, setJobQuery] = useState('')
  const [jobDropdownOpen, setJobDropdownOpen] = useState(false)
  const [selectedJob, setSelectedJob] = useState<JobOption | null>(null)
  const cvInputRef = useRef<HTMLInputElement>(null)
  const testInputRef = useRef<HTMLInputElement>(null)
  const jobInputRef = useRef<HTMLInputElement>(null)

  const filteredJobs = jobs.filter(j =>
    j.title.toLowerCase().includes(jobQuery.toLowerCase())
  )

  function handleJobSelect(job: JobOption) {
    setSelectedJob(job)
    setJobQuery(job.title)
    setJobDropdownOpen(false)
    setForm(f => ({ ...f, jobTitle: job.title, jobId: job.key }))
  }

  function handleJobQueryChange(val: string) {
    setJobQuery(val)
    setJobDropdownOpen(true)
    setSelectedJob(null)
    setForm(f => ({ ...f, jobTitle: val, jobId: '' }))
  }

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (jobInputRef.current && !jobInputRef.current.closest('.job-autocomplete')?.contains(e.target as Node)) {
        setJobDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function set(key: keyof FormValues, value: string | File | null) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleTestFileAccept(file: File) {
    set('testFile', file)
    setTestParsed(null)
    setTestParseError(null)
    setTestParsing(true)

    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch('/api/test/parse', { method: 'POST', body: fd })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'Parse failed')
      }
      const data: ParsedTest = await res.json()
      setTestParsed(data)
      setForm((f) => ({
        ...f,
        testFile: file,
        testResultsJson: JSON.stringify(data.scores),
        targetSkills: data.target_skills.join(', '),
      }))
    } catch (e: any) {
      setTestParseError(e.message || 'Could not parse test sheet')
    } finally {
      setTestParsing(false)
    }
  }

  async function handleCvFileAccept(file: File) {
    set('cvFile', file)
    setCvParsed(false)
    setCvParseError(null)
    setCvParsing(true)

    try {
      const fd = new FormData()
      fd.append('file', file)
      // source_key optional — backend falls back to env HRFLOW_SOURCE_KEY
      const res = await fetch('/api/cv/parse', { method: 'POST', body: fd })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'CV parse failed')
      }
      const data = await res.json()
      setCvParsed(true)
      setForm((f) => ({
        ...f,
        cvFile: file,
        // Only auto-fill if the user hasn't typed a name already
        candidateName: f.candidateName.trim() === '' ? (data.full_name || '') : f.candidateName,
        // Auto-generate ID from profile_key (short prefix) if not filled
        candidateId: f.candidateId.trim() === ''
          ? (data.profile_key ? `cand_${data.profile_key.slice(0, 8)}` : `cand_${Date.now()}`)
          : f.candidateId,
      }))
    } catch (e: any) {
      setCvParseError(e.message || 'Could not parse CV')
      setCvParsed(false)
    } finally {
      setCvParsing(false)
    }
  }

  function handleCvDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setCvDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleCvFileAccept(file)
  }

  function handleTestDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setTestDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleTestFileAccept(file)
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
    !testParsing

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
                <label className="label">
                  Full name
                  {cvParsing && (
                    <span className="ml-2 text-xs text-slate-400 font-normal">parsing CV…</span>
                  )}
                  {cvParsed && form.candidateName && (
                    <span className="ml-2 text-xs text-green-600 font-normal">✓ auto-filled from CV</span>
                  )}
                </label>
                <input
                  className={`input-field ${cvParsed && form.candidateName ? 'border-green-300 focus:border-green-400' : ''}`}
                  placeholder="Filled automatically after CV upload"
                  value={form.candidateName}
                  onChange={e => set('candidateName', e.target.value)}
                />
              </div>
              <div>
                <label className="label">
                  Candidate ID
                  {cvParsed && form.candidateId && (
                    <span className="ml-2 text-xs text-green-600 font-normal">✓ auto-generated</span>
                  )}
                </label>
                <input
                  className={`input-field font-mono text-xs ${cvParsed && form.candidateId ? 'border-green-300 focus:border-green-400' : ''}`}
                  placeholder="Auto-generated after CV upload"
                  value={form.candidateId}
                  onChange={e => set('candidateId', e.target.value)}
                />
              </div>
              {cvParseError && (
                <p className="text-xs text-amber-600">⚠ Could not auto-fill: {cvParseError}. Fill manually.</p>
              )}
            </div>
          </div>

          {/* Job — autocomplete */}
          <div className="card">
            <p className="section-title">Target job</p>
            <div className="job-autocomplete relative">
              <label className="label">
                Job title <span className="text-red-400">*</span>
                {jobs.length > 0 && (
                  <span className="ml-2 text-xs font-normal text-slate-400">{jobs.length} jobs available</span>
                )}
              </label>
              <input
                ref={jobInputRef}
                className={`input-field ${selectedJob ? 'border-brand-400' : ''}`}
                placeholder={jobs.length === 0 ? 'Loading jobs…' : 'Type to search a job…'}
                value={jobQuery}
                onChange={e => handleJobQueryChange(e.target.value)}
                onFocus={() => setJobDropdownOpen(true)}
                autoComplete="off"
              />
              {/* Dropdown */}
              {jobDropdownOpen && filteredJobs.length > 0 && (
                <ul className="absolute z-20 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-lg max-h-48 overflow-y-auto">
                  {filteredJobs.map(job => (
                    <li
                      key={job.key}
                      className="flex flex-col px-3 py-2.5 cursor-pointer hover:bg-brand-50 border-b border-slate-50 last:border-0"
                      onMouseDown={() => handleJobSelect(job)}
                    >
                      <span className="text-sm font-medium text-slate-700">{job.title}</span>
                      {job.skills.length > 0 && (
                        <span className="text-xs text-slate-400 mt-0.5 truncate">
                          {job.skills.slice(0, 5).join(' · ')}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {jobDropdownOpen && jobQuery.length > 0 && filteredJobs.length === 0 && (
                <div className="absolute z-20 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow px-3 py-2 text-xs text-slate-400">
                  No matching job found
                </div>
              )}
            </div>

            {/* Required skills hint */}
            {selectedJob && selectedJob.skills.length > 0 && (
              <div className="mt-3 rounded-lg bg-brand-50 border border-brand-100 p-3">
                <p className="text-xs font-medium text-brand-700 mb-1.5">
                  Required skills for this position
                  <span className="ml-1 font-normal text-brand-500">— your test sheet should cover these</span>
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {selectedJob.skills.map((skill, i) => (
                    <span key={i} className="inline-block rounded-full border border-brand-200 bg-white px-2.5 py-0.5 text-xs text-brand-700 font-medium">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* CV Upload */}
          <div className="card">
            <p className="section-title">Resume / CV <span className="text-red-400">*</span></p>
            <DropZone
              file={form.cvFile}
              dragging={cvDragging}
              accept=".pdf,.doc,.docx,.txt"
              hint="PDF, DOCX — max 10 MB"
              inputRef={cvInputRef}
              onDragOver={() => setCvDragging(true)}
              onDragLeave={() => setCvDragging(false)}
              onDrop={handleCvDrop}
              onFileChange={handleCvFileAccept}
              loading={cvParsing}
            />
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">

          {/* Test sheet upload */}
          <div className="card">
            <p className="section-title">
              Technical test sheet <span className="text-red-400">*</span>
              <span className="ml-2 font-normal normal-case text-xs text-slate-400">
                PDF or text — skills & scores extracted automatically
              </span>
            </p>
            <DropZone
              file={form.testFile}
              dragging={testDragging}
              accept=".pdf,.txt,.md,.csv"
              hint="PDF or text file — scores parsed by AI"
              inputRef={testInputRef}
              onDragOver={() => setTestDragging(true)}
              onDragLeave={() => setTestDragging(false)}
              onDrop={handleTestDrop}
              onFileChange={handleTestFileAccept}
              loading={testParsing}
            />

            {/* Parse result preview */}
            {testParsing && (
              <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
                Parsing test sheet…
              </div>
            )}
            {testParseError && (
              <p className="mt-2 text-xs text-red-500">{testParseError}</p>
            )}
            {testParsed && !testParsing && (
              <div className="mt-3 rounded-lg bg-green-50 border border-green-200 p-3 space-y-2">
                <p className="text-xs font-medium text-green-700">Detected {Object.keys(testParsed.scores).length} competencies</p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(testParsed.scores).map(([k, v]) => (
                    <span key={k} className="inline-flex items-center gap-1 rounded-full border border-green-200 bg-white px-2 py-0.5 text-xs text-slate-600">
                      <span className="font-medium">{k.split('.').pop()}</span>
                      <span className="text-green-600 font-semibold">{v}/5</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
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

// ---------------------------------------------------------------------------
// Reusable drop-zone component
// ---------------------------------------------------------------------------

interface DropZoneProps {
  file: File | null
  dragging: boolean
  accept: string
  hint: string
  inputRef: RefObject<HTMLInputElement>
  onDragOver: () => void
  onDragLeave: () => void
  onDrop: (e: DragEvent<HTMLDivElement>) => void
  onFileChange: (f: File) => void
  loading?: boolean
}

function DropZone({ file, dragging, accept, hint, inputRef, onDragOver, onDragLeave, onDrop, onFileChange, loading }: DropZoneProps) {
  return (
    <div
      className={`relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed
                  px-6 py-8 text-center cursor-pointer transition-colors
                  ${dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 hover:border-brand-400 hover:bg-slate-50'}`}
      onDragOver={(e) => { e.preventDefault(); onDragOver() }}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input ref={inputRef} type="file" className="hidden" accept={accept}
        onChange={(e: ChangeEvent<HTMLInputElement>) => {
          const f = e.target.files?.[0]
          if (f) onFileChange(f)
        }} />
      {file ? (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-brand-100 flex items-center justify-center">
            {loading ? (
              <svg className="w-5 h-5 text-brand-600 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
            ) : (
              <svg className="w-5 h-5 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0119 9.414V19a2 2 0 01-2 2z" />
              </svg>
            )}
          </div>
          <div className="text-left">
            <p className="text-sm font-medium text-slate-700">{file.name}</p>
            <p className="text-xs text-slate-400">{(file.size / 1024).toFixed(0)} KB — click to change</p>
          </div>
        </div>
      ) : (
        <>
          <svg className="w-8 h-8 text-slate-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-sm font-medium text-slate-600">Drop file here or click to browse</p>
          <p className="text-xs text-slate-400 mt-1">{hint}</p>
        </>
      )}
    </div>
  )
}
