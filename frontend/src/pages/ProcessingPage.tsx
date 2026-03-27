import { useEffect, useState } from 'react'

const STEPS = [
  {
    id: 'cv_parsed',
    label: 'Parsing CV via HrFlow',
    description: 'Extracting skills, experience, education…',
    delay: 400,
  },
  {
    id: 'profile_scored',
    label: 'Scoring profile against job',
    description: 'Running HrFlow GET /v1/profiles/scoring…',
    delay: 2200,
  },
  {
    id: 'interview_extracted',
    label: 'Extracting interview signals',
    description: 'Claude Agent 1 — parsing recruiter notes…',
    delay: 4000,
  },
  {
    id: 'fusion_completed',
    label: 'Building fusion object',
    description: 'Weighted combination of CV + test + interview…',
    delay: 6000,
  },
  {
    id: 'synthesis_generated',
    label: 'Generating candidate synthesis',
    description: 'Claude Agent 2 — final evaluation report…',
    delay: 7500,
  },
]

export default function ProcessingPage() {
  const [visible, setVisible] = useState<Set<string>>(new Set())

  useEffect(() => {
    const timers = STEPS.map(step =>
      setTimeout(() => {
        setVisible(v => new Set([...v, step.id]))
      }, step.delay),
    )
    return () => timers.forEach(clearTimeout)
  }, [])

  return (
    <div className="max-w-xl mx-auto py-12">
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-brand-100 mb-4">
          <svg className="w-7 h-7 text-brand-600 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-slate-800">Running pipeline…</h2>
        <p className="text-sm text-slate-500 mt-1">This takes 15–30 seconds</p>
      </div>

      <div className="space-y-3">
        {STEPS.map((step, i) => {
          const isVisible = visible.has(step.id)
          const isActive = isVisible && i === [...visible].map(id => STEPS.findIndex(s => s.id === id)).sort().at(-1)

          return (
            <div
              key={step.id}
              className={`flex items-start gap-4 rounded-xl border px-5 py-4 transition-all duration-500
                ${isVisible
                  ? 'border-slate-200 bg-white shadow-sm opacity-100 translate-y-0'
                  : 'border-transparent bg-transparent opacity-0 translate-y-2 pointer-events-none'}`}
            >
              {/* Icon */}
              <div className={`mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full
                ${isActive ? 'bg-brand-100' : 'bg-green-100'}`}>
                {isActive ? (
                  <span className="pulse-dot h-2 w-2 rounded-full bg-brand-500" />
                ) : (
                  <svg className="w-3.5 h-3.5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>

              {/* Text */}
              <div>
                <p className={`text-sm font-semibold ${isActive ? 'text-brand-700' : 'text-slate-700'}`}>
                  {step.label}
                </p>
                <p className="text-xs text-slate-400">{step.description}</p>
              </div>

              {/* Step number */}
              <span className="ml-auto text-xs text-slate-300 font-mono">{i + 1}/{STEPS.length}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
