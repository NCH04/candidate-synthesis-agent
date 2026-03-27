import { useState } from 'react'
import { FormValues, PipelineResult } from './types'
import InputPage from './pages/InputPage'
import ProcessingPage from './pages/ProcessingPage'
import ResultsPage from './pages/ResultsPage'
import { runFullPipeline } from './api/pipeline'

type View = 'input' | 'processing' | 'results'

export default function App() {
  const [view, setView] = useState<View>('input')
  const [result, setResult] = useState<PipelineResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(form: FormValues) {
    setError(null)
    setView('processing')
    try {
      const data = await runFullPipeline(form)
      setResult(data)
      setView('results')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setView('input')
    }
  }

  function handleReset() {
    setResult(null)
    setError(null)
    setView('input')
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
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
              <p className="text-xs text-slate-400">Powered by HrFlow + Claude</p>
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
          {(['input', 'processing', 'results'] as View[]).map((step, i) => {
            const labels = ['1. Input', '2. Processing', '3. Results']
            const active = view === step
            const done =
              (step === 'input' && view !== 'input') ||
              (step === 'processing' && view === 'results')
            return (
              <div key={step} className="flex items-center gap-2">
                <span className={`flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold
                  ${done ? 'bg-green-500 text-white' : active ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500'}`}>
                  {done ? '✓' : i + 1}
                </span>
                <span className={`text-xs font-medium ${active ? 'text-brand-600' : done ? 'text-green-600' : 'text-slate-400'}`}>
                  {labels[i]}
                </span>
                {i < 2 && <span className="text-slate-200 text-xs">›</span>}
              </div>
            )
          })}
        </div>
      </div>

      {/* Main content */}
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

        {view === 'input' && <InputPage onSubmit={handleSubmit} />}
        {view === 'processing' && <ProcessingPage />}
        {view === 'results' && result && (
          <ResultsPage result={result} onReset={handleReset} />
        )}
      </main>
    </div>
  )
}
