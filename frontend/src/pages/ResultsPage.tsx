import { PipelineResult, DecisionType, ConfidenceLevel } from '../types'

interface Props {
  result: PipelineResult
  onReset: () => void
}

/* ─── helpers ─────────────────────────────────────────────────────────────── */

function scoreColor(pct: number) {
  if (pct >= 70) return { ring: 'ring-green-400', text: 'text-green-600', bg: 'bg-green-50' }
  if (pct >= 50) return { ring: 'ring-amber-400', text: 'text-amber-600', bg: 'bg-amber-50' }
  return { ring: 'ring-red-400', text: 'text-red-500', bg: 'bg-red-50' }
}

function DecisionBlock({ decision }: { decision: DecisionType }) {
  const cfg: Record<DecisionType, { bg: string; text: string; border: string; icon: string; label: string }> = {
    'Hire': {
      bg: 'bg-green-500', text: 'text-white', border: 'border-green-600',
      icon: '✓', label: 'HIRE',
    },
    'Consider': {
      bg: 'bg-amber-400', text: 'text-white', border: 'border-amber-500',
      icon: '~', label: 'CONSIDER',
    },
    'No Hire': {
      bg: 'bg-red-500', text: 'text-white', border: 'border-red-600',
      icon: '✕', label: 'NO HIRE',
    },
  }
  const c = cfg[decision]
  return (
    <div className={`inline-flex items-center gap-2 rounded-xl px-5 py-2.5 ${c.bg} ${c.text} border ${c.border} shadow`}>
      <span className="text-xl font-bold">{c.icon}</span>
      <span className="text-lg font-extrabold tracking-wide">{c.label}</span>
    </div>
  )
}

function ScoreCircle({ value, max = 1, label, size = 'md' }: {
  value: number; max?: number; label: string; size?: 'sm' | 'md' | 'lg'
}) {
  const pct = Math.round((value / max) * 100)
  const c = scoreColor(pct)
  const sizes = {
    sm:  { ring: 'w-16 h-16 ring-2',  num: 'text-xl',  lbl: 'text-xs' },
    md:  { ring: 'w-20 h-20 ring-2',  num: 'text-2xl', lbl: 'text-xs' },
    lg:  { ring: 'w-28 h-28 ring-4',  num: 'text-4xl', lbl: 'text-sm' },
  }
  const s = sizes[size]
  return (
    <div className="flex flex-col items-center gap-2">
      <div className={`${s.ring} ${c.ring} ${c.bg} rounded-full flex flex-col items-center justify-center`}>
        <span className={`${s.num} font-extrabold ${c.text} leading-none`}>{pct}</span>
        <span className={`text-[10px] font-medium ${c.text} opacity-70`}>/ 100</span>
      </div>
      <span className={`${s.lbl} font-semibold text-slate-500 text-center leading-tight`}>{label}</span>
    </div>
  )
}

function TagList({ items, variant }: { items: string[]; variant: 'green' | 'red' | 'amber' | 'blue' }) {
  const styles = {
    green: 'bg-green-50 text-green-700 border-green-200',
    red:   'bg-red-50 text-red-700 border-red-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    blue:  'bg-blue-50 text-blue-700 border-blue-200',
  }
  if (!items?.length) return <p className="text-xs text-slate-400 italic">None identified</p>
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item, i) => (
        <span key={i} className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium ${styles[variant]}`}>
          {item}
        </span>
      ))}
    </div>
  )
}

function SkillChip({ label, matched }: { label: string; matched: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium
      ${matched ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-600 border-red-200'}`}>
      <span>{matched ? '✓' : '✕'}</span>
      {label}
    </span>
  )
}

function nextSteps(decision: DecisionType, weaknesses: string[]): { icon: string; text: string }[] {
  if (decision === 'Hire') {
    return [
      { icon: '📞', text: 'Schedule offer call with HR' },
      { icon: '📋', text: 'Notify hiring manager — attach this report' },
      { icon: '🚀', text: 'Prepare onboarding plan and equipment request' },
    ]
  }
  if (decision === 'Consider') {
    const deepDive = weaknesses[0]
      ? `Schedule 2nd technical interview focused on: ${weaknesses[0]}`
      : 'Schedule 2nd round technical interview'
    return [
      { icon: '🔍', text: deepDive },
      { icon: '📞', text: 'Request professional references (2 minimum)' },
      { icon: '🤝', text: 'Arrange team culture-fit conversation' },
    ]
  }
  return [
    { icon: '✉️', text: 'Send personalised rejection with constructive feedback' },
    { icon: '📁', text: 'Add to talent pool — revisit for junior openings' },
    { icon: '📝', text: 'Document evaluation for recruiter notes' },
  ]
}

/* ─── main component ──────────────────────────────────────────────────────── */

export default function ResultsPage({ result, onReset }: Props) {
  const { synthesis_report: r, assessment: a } = result
  const dim = a.fusion_summary.dimension_scores
  const candidate = a.candidate_context.candidate_name || 'Candidate'
  const jobTitle  = a.job_context.job_title || 'Position'
  const today     = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  const overallPct = Math.round(r.overall_score * 100)
  const steps = nextSteps(r.decision, r.weaknesses)

  return (
    <div className="space-y-5 pb-10">

      {/* ── 1. HERO CARD ─────────────────────────────────────────────────── */}
      <div className={`card border-l-4 ${
        r.decision === 'Hire' ? 'border-l-green-500' :
        r.decision === 'Consider' ? 'border-l-amber-400' : 'border-l-red-500'
      }`}>
        {/* top meta */}
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400 mb-4">
          <span className="font-semibold text-slate-600 text-sm">{candidate}</span>
          <span>·</span>
          <span>{jobTitle}</span>
          <span>·</span>
          <span>{today}</span>
          <span className="ml-auto">
            {Object.entries(result.pipeline_steps).map(([key, done]) => (
              <span key={key} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium mr-1
                ${done ? 'bg-green-50 border-green-200 text-green-700' : 'bg-slate-50 border-slate-200 text-slate-400'}`}>
                {done ? '✓' : '○'} {key.replace(/_/g, ' ')}
              </span>
            ))}
          </span>
        </div>

        {/* content row */}
        <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
          {/* big score */}
          <ScoreCircle value={r.overall_score} label="Overall score" size="lg" />

          {/* summary + verdict */}
          <div className="flex-1 space-y-3">
            <p className="text-slate-700 text-sm leading-relaxed">{r.executive_summary}</p>
            <div className="flex flex-wrap items-center gap-3">
              <DecisionBlock decision={r.decision} />
              <span className={`rounded-full px-3 py-1 text-xs font-semibold border
                ${r.confidence_level === 'High'   ? 'bg-blue-50 text-blue-700 border-blue-200' :
                  r.confidence_level === 'Medium' ? 'bg-slate-100 text-slate-600 border-slate-200' :
                  'bg-orange-50 text-orange-600 border-orange-200'}`}>
                {r.confidence_level} confidence
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── 2. DIMENSION SCORES ──────────────────────────────────────────── */}
      <div className="card">
        <p className="section-title mb-4">Score breakdown
          <span className="ml-2 font-normal normal-case text-slate-400 text-xs">CV 35% · Test 40% · Interview 25%</span>
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 justify-items-center">
          <ScoreCircle value={dim.technical_fit}     label="Technical fit"    size="md" />
          <ScoreCircle value={dim.motivation_fit}    label="Motivation"       size="md" />
          <ScoreCircle value={dim.communication_fit} label="Communication"    size="md" />
          <ScoreCircle value={dim.overall_score}     label="Weighted overall" size="md" />
        </div>
      </div>

      {/* ── 3. STRENGTHS / WEAKNESSES / RISKS ───────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card">
          <p className="section-title text-green-600 mb-2">Strengths</p>
          <TagList items={r.strengths} variant="green" />
        </div>
        <div className="card">
          <p className="section-title text-red-500 mb-2">Weaknesses</p>
          <TagList items={r.weaknesses} variant="red" />
        </div>
        <div className="card">
          <p className="section-title text-amber-500 mb-2">Risk factors</p>
          <TagList items={r.risks} variant="amber" />
        </div>
      </div>

      {/* ── 4. SKILLS MATCH + TEST SCORES ───────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

        {/* skills gap */}
        <div className="card">
          <p className="section-title mb-3">
            Skills match
            <span className="ml-2 font-normal normal-case text-slate-400 text-xs">
              {a.cv_profile_matching.matched_skills.length}/{a.cv_profile_matching.matched_skills.length + a.cv_profile_matching.missing_skills.length} matched
              · HrFlow {a.cv_profile_matching.score.toFixed(0)}/100
            </span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {a.cv_profile_matching.matched_skills.map(s => <SkillChip key={s} label={s} matched />)}
            {a.cv_profile_matching.missing_skills.map(s => <SkillChip key={s} label={s} matched={false} />)}
          </div>
          <p className="mt-2 text-xs text-slate-500 italic">Experience fit: {a.cv_profile_matching.experience_fit}</p>
        </div>

        {/* test scores */}
        <div className="card">
          <p className="section-title mb-3">Test assessment</p>
          <div className="grid grid-cols-3 gap-3 mb-3">
            {[
              { label: 'Technical',   value: a.test_assessment.aggregated_scores.technical_score },
              { label: 'Soft skills', value: a.test_assessment.aggregated_scores.soft_skills_score },
              { label: 'Motivation',  value: a.test_assessment.aggregated_scores.motivation_score },
            ].map(({ label, value }) => {
              const c = scoreColor(value * 20)
              return (
                <div key={label} className={`rounded-xl p-3 text-center ${c.bg} ring-1 ${c.ring}`}>
                  <p className={`text-2xl font-extrabold ${c.text}`}>{value.toFixed(1)}</p>
                  <p className="text-[10px] text-slate-400 font-medium">/ 5</p>
                  <p className={`text-xs font-semibold ${c.text} mt-0.5`}>{label}</p>
                </div>
              )
            })}
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">{a.test_assessment.summary}</p>
        </div>
      </div>

      {/* ── 5. DOMAIN FIT ────────────────────────────────────────────────── */}
      {r.domain_fit && (
        <div className="card border-l-4 border-l-blue-400">
          <p className="section-title text-blue-600 mb-1">Domain fit</p>
          <p className="text-sm text-slate-700 leading-relaxed">{r.domain_fit}</p>
        </div>
      )}

      {/* ── 6. BEHAVIORAL ───────────────────────────────────────────────── */}
      <div className="card">
        <p className="section-title mb-1">Behavioural & motivation</p>
        <p className="text-sm text-slate-600 leading-relaxed">{r.behavioral_assessment}</p>
      </div>

      {/* ── 8. JUSTIFICATION ─────────────────────────────────────────────── */}
      <div className="card bg-slate-50 border-slate-200">
        <p className="section-title mb-2">Justification</p>
        <p className="text-sm text-slate-700 leading-relaxed line-clamp-4">{r.justification}</p>
      </div>

      {/* ── 9. RECOMMENDED NEXT STEPS ───────────────────────────────────── */}
      <div className={`card border-l-4 ${
        r.decision === 'Hire' ? 'border-l-green-500 bg-green-50/40' :
        r.decision === 'Consider' ? 'border-l-amber-400 bg-amber-50/40' :
        'border-l-red-400 bg-red-50/30'
      }`}>
        <p className="section-title mb-3">Recommended next steps</p>
        <div className="space-y-2.5">
          {steps.map((s, i) => (
            <div key={i} className="flex items-start gap-3 text-sm text-slate-700">
              <span className="text-base mt-0.5">{s.icon}</span>
              <span className="leading-snug">{s.text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── ACTIONS ──────────────────────────────────────────────────────── */}
      <div className="flex justify-between items-center pt-2">
        <button onClick={onReset} className="btn-ghost">
          ← Evaluate another candidate
        </button>
        <button onClick={() => window.print()} className="btn-ghost text-slate-500">
          🖨 Print / Export
        </button>
      </div>

    </div>
  )
}
