import { useEffect, useRef, useState } from 'react'
import { CandidateAssessment, SynthesisReport } from '../types'
import { streamSynthesis } from '../api/pipeline'

interface Props {
  assessment: CandidateAssessment
  onComplete: (report: SynthesisReport) => void
  onError: (msg: string) => void
}

export default function StreamingPage({ assessment, onComplete, onError }: Props) {
  const [accumulated, setAccumulated] = useState('')
  const [phase, setPhase] = useState<'draft' | 'critic' | 'fairness'>('draft')
  const scrollerRef = useRef<HTMLDivElement>(null)
  const startedRef = useRef(false)

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true

    streamSynthesis(
      assessment,
      (delta) => {
        setAccumulated((prev) => prev + delta)
      },
      (report) => {
        // The 'final' event arrives after critic + fairness — done.
        onComplete(report as SynthesisReport)
      },
      (msg) => onError(msg),
    )
  }, [assessment, onComplete, onError])

  // After ~6s of accumulation, the draft is done and critic kicks in
  useEffect(() => {
    const t1 = setTimeout(() => setPhase('critic'), 8000)
    const t2 = setTimeout(() => setPhase('fairness'), 14000)
    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
    }
  }, [])

  // Auto-scroll the live text panel
  useEffect(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight
    }
  }, [accumulated])

  const phaseLabel = {
    draft: 'Drafting synthesis…',
    critic: 'Refining (critic agent)…',
    fairness: 'Fairness review…',
  }[phase]

  return (
    <div className="max-w-2xl mx-auto py-10 space-y-6">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-brand-100 mb-3">
          <svg className="w-7 h-7 text-brand-600 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9.75 17 9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2Z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-slate-800">{phaseLabel}</h2>
        <p className="text-sm text-slate-500 mt-1">Claude is producing the synthesis live</p>
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
        Once the draft is complete, a critic agent will review it for consistency and a fairness
        agent will flag any non-job-relevant content.
      </p>
    </div>
  )
}
