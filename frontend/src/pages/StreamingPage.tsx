import { useEffect, useRef, useState } from 'react'
import { CandidateAssessment, SynthesisReport } from '../types'
import { streamSynthesis, SynthesisPhase } from '../api/pipeline'

interface Props {
  assessment: CandidateAssessment
  onComplete: (report: SynthesisReport) => void
  onError: (msg: string) => void
}

const PHASE_LABEL: Record<SynthesisPhase, string> = {
  draft: 'Drafting synthesis…',
  'draft-retry': 'Draft was malformed — regenerating…',
  critic: 'Refining (critic agent)…',
  fairness: 'Fairness review…',
  done: 'Finalising report…',
}

// Ordered pipeline stages shown as a checklist. `draft-retry` is a recovery
// state, not a stage, so it is not listed here.
const PHASE_STEPS: { id: SynthesisPhase; label: string }[] = [
  { id: 'draft', label: 'Draft synthesis' },
  { id: 'critic', label: 'Critic review' },
  { id: 'fairness', label: 'Fairness check' },
]

export default function StreamingPage({ assessment, onComplete, onError }: Props) {
  const [accumulated, setAccumulated] = useState('')
  // Driven by the server's `phase` events — never by a timer. The UI used to
  // fake these transitions at 8s and 14s regardless of what the backend did.
  const [phase, setPhase] = useState<SynthesisPhase>('draft')
  const scrollerRef = useRef<HTMLDivElement>(null)
  const startedRef = useRef(false)

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true

    streamSynthesis(assessment, {
      onDelta: (delta) => setAccumulated((prev) => prev + delta),
      onPhase: setPhase,
      onFinal: (report) => onComplete(report as SynthesisReport),
      onError,
    }).catch((err: unknown) =>
      onError(err instanceof Error ? err.message : 'Stream failed'),
    )
  }, [assessment, onComplete, onError])

  // Auto-scroll the live text panel
  useEffect(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight
    }
  }, [accumulated])

  const activeIdx = PHASE_STEPS.findIndex(s => s.id === phase)
  const reachedIdx = phase === 'done' ? PHASE_STEPS.length : activeIdx

  return (
    <div className="max-w-2xl mx-auto py-10 space-y-6">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-brand-100 mb-3">
          <svg className="w-7 h-7 text-brand-600 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9.75 17 9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2Z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-slate-800">{PHASE_LABEL[phase]}</h2>
        <p className="text-sm text-slate-500 mt-1">Claude is producing the synthesis live</p>
      </div>

      {/* Real pipeline stages, reported by the server */}
      <div className="flex items-center justify-center gap-2 text-xs">
        {PHASE_STEPS.map((step, i) => {
          const done = i < reachedIdx
          const active = i === reachedIdx
          return (
            <div key={step.id} className="flex items-center gap-2">
              <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold
                ${done ? 'bg-green-500 text-white' : active ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500'}`}>
                {done ? '✓' : i + 1}
              </span>
              <span className={`font-medium ${active ? 'text-brand-600' : done ? 'text-green-600' : 'text-slate-400'}`}>
                {step.label}
              </span>
              {i < PHASE_STEPS.length - 1 && <span className="text-slate-200">›</span>}
            </div>
          )
        })}
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Live stream</p>
          <span className="text-xs text-slate-400">{accumulated.length} chars</span>
        </div>
        <div
          ref={scrollerRef}
          className="h-72 overflow-y-auto rounded-md bg-slate-900 p-4 font-mono text-[11px] leading-relaxed text-green-300 whitespace-pre-wrap"
        >
          {accumulated || <span className="text-slate-500">Waiting for first token…</span>}
          <span className="inline-block w-2 h-3 bg-green-300 animate-pulse ml-0.5 align-middle" />
        </div>
      </div>

      <p className="text-center text-xs text-slate-400">
        Once the draft is complete, a critic agent reviews it for consistency and a fairness
        agent flags any non-job-relevant content.
      </p>
    </div>
  )
}
