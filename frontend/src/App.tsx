import { useState, useEffect, useCallback } from 'react'
import { CandidateAssessment, FormValues, JobOption, PipelineResult, SynthesisReport } from './types'
import InputPage from './pages/InputPage'
import ProcessingPage from './pages/ProcessingPage'
import StreamingPage from './pages/StreamingPage'
import ResultsPage from './pages/ResultsPage'
import { preparePipeline } from './api/pipeline'
import { fetchJobs } from './api/jobs'

type View = 'input' | 'processing' | 'streaming' | 'results'

export default function App() {
  const [view, setView] = useState<View>('input')
  const [assessment, setAssessment] = useState<CandidateAssessment | null>(null)
  const [result, setResult] = useState<PipelineResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [jobs, setJobs] = useState<JobOption[]>([])

  useEffect(() => {
    fetchJobs().then(setJobs)
  }, [])

  async function handleSubmit(form: FormValues) {
    setError(null)
    setResult(null)
    setAssessment(null)
    setView('processing')
    try {
      const a = await preparePipeline(form)
      setAssessment(a)
      setView('streaming')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setView('input')
    }
  }

  const handleStreamComplete = useCallback(
    (report: SynthesisReport) => {
      if (!assessment) return
      setResult({
        pipeline_steps: {
          cv_parsed: true,
          profile_scored: true,
          interview_extracted: true,
          fusion_completed: true,
          synthesis_generated: true,
          critic_refined: true,
          fairness_checked: !!report.fairness,
        },
        assessment,
        synthesis_report: report,
      })
      setView('results')
    },
    [assessment],
  )

  const handleStreamError = useCallback((msg: string) => {
    setError(msg)
    setView('input')
  }, [])

  function handleReset() {
    setResult(null)
    setAssessment(null)
    setError(null)
    setView('input')
  }

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="font-semibold text-slate-800 text-sm leading-tight">AI Candidate Synthesis</p>
              <p className="text-xs text-slate-400">Multi-agent recruitment pipeline · Powered by Claude</p>
            </div>
          </div>
          {view !== 'input' && (
            <button onClick={handleReset} className="btn-ghost text-xs">
              ← New evaluation
            </button>
          )}
        </div>
      </header>

      {/* Step indicator */}
      <div className="bg-white border-b border-slate-100">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center gap-6">
          {(['input', 'processing', 'streaming', 'results'] as View[]).map((step, i) => {
            const labels = ['1. Input', '2. Processing', '3. Synthesis', '4. Results']
            const order: View[] = ['input', 'processing', 'streaming', 'results']
            const currentIdx = order.indexOf(view)
            const stepIdx = order.indexOf(step)
            const active = view === step
            const done = stepIdx < currentIdx
            return (
              <div key={step} className="flex items-center gap-2">
                <span className={`flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold
                  ${done ? 'bg-green-500 text-white' : active ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500'}`}>
                  {done ? '✓' : i + 1}
                </span>
                <span className={`text-xs font-medium ${active ? 'text-brand-600' : done ? 'text-green-600' : 'text-slate-400'}`}>
                  {labels[i]}
                </span>
                {i < 3 && <span className="text-slate-200 text-xs">›</span>}
              </div>
            )
          })}
        </div>
      </div>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {error && (
          <div className="mb-6 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 flex gap-2 items-start">
            <span className="mt-0.5">⚠</span>
            <div>
              <p className="font-semibold">Pipeline error</p>
              <p className="text-red-600">{error}</p>
            </div>
          </div>
        )}

        {view === 'input' && <InputPage onSubmit={handleSubmit} jobs={jobs} />}
        {view === 'processing' && <ProcessingPage />}
        {view === 'streaming' && assessment && (
          <StreamingPage
            assessment={assessment}
            onComplete={handleStreamComplete}
            onError={handleStreamError}
          />
        )}
        {view === 'results' && result && (
          <ResultsPage result={result} onReset={handleReset} />
        )}
      </main>
    </div>
  )
}
