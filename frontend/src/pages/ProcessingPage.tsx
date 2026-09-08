const STEPS = [
  {
    id: 'cv_parsed',
    label: 'Parsing CV',
    description: 'Claude — extracting skills, experience, education…',
  },
  {
    id: 'profile_scored',
    label: 'Scoring profile against job',
    description: 'Semantic skill match + Claude fit evaluation…',
  },
  {
    id: 'interview_extracted',
    label: 'Extracting interview signals',
    description: 'Claude — parsing recruiter notes…',
  },
  {
    id: 'fusion_completed',
    label: 'Building fusion object',
    description: 'Weighted combination of CV + test + interview…',
  },
]

/**
 * The prepare phase is a single request, so the server reports no intermediate
 * progress for it. The steps below are therefore presented as "what is running"
 * — not as a checklist that ticks itself off on a timer, which is what this
 * screen used to do regardless of the backend's actual state.
 *
 * The synthesis phase *does* report real progress: see StreamingPage.
 */
export default function ProcessingPage() {
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
        <h2 className="text-xl font-bold text-slate-800">Building candidate assessment…</h2>
        <p className="text-sm text-slate-500 mt-1">Once ready, the synthesis will stream live</p>
      </div>

      <div className="space-y-3">
        {STEPS.map((step, i) => (
          <div
            key={step.id}
            className="flex items-start gap-4 rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-sm"
          >
            <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-brand-100">
              <span className="pulse-dot h-2 w-2 rounded-full bg-brand-500" />
            </div>

            <div>
              <p className="text-sm font-semibold text-slate-700">{step.label}</p>
              <p className="text-xs text-slate-400">{step.description}</p>
            </div>

            <span className="ml-auto text-xs text-slate-300 font-mono">{i + 1}/{STEPS.length}</span>
          </div>
        ))}
      </div>

      <p className="mt-6 text-center text-xs text-slate-400">
        These four steps run server-side in a single request.
      </p>
    </div>
  )
}
