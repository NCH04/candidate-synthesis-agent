import { PipelineResult, DecisionType, ConfidenceLevel } from '../types'

interface Props {
  result: PipelineResult
  onReset: () => void
}

function ScoreBar({ value, max = 1, color = 'brand' }: { value: number; max?: number; color?: string }) {
  const pct = Math.round((value / max) * 100)
  const colorClass =
    color === 'green' ? 'bg-green-500' :
    color === 'red' ? 'bg-red-400' :
    color === 'amber' ? 'bg-amber-400' : 'bg-brand-500'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full bg-slate-100">
        <div className={`h-2 rounded-full transition-all ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-500 w-8 text-right">{pct}%</span>
    </div>
  )
}

function DecisionBadge({ decision }: { decision: DecisionType }) {
  const styles: Record<DecisionType, string> = {
    'Hire': 'bg-green-100 text-green-800 border-green-200',
    'Consider': 'bg-amber-100 text-amber-800 border-amber-200',
    'No Hire': 'bg-red-100 text-red-700 border-red-200',
  }
  const icons: Record<DecisionType, string> = {
    'Hire': '✓',
    'Consider': '~',
    'No Hire': '✕',
  }
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold ${styles[decision]}`}>
      <span>{icons[decision]}</span>
      {decision}
    </span>
  )
}

function ConfidenceBadge({ level }: { level: ConfidenceLevel }) {
  const styles: Record<ConfidenceLevel, string> = {
    'High': 'bg-blue-100 text-blue-700',
    'Medium': 'bg-slate-100 text-slate-600',
    'Low': 'bg-orange-100 text-orange-700',
  }
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[level]}`}>
      {level} confidence
    </span>
  )
}

function TagList({ items, variant }: { items: string[]; variant: 'green' | 'red' | 'amber' | 'blue' }) {
  const styles = {
    green: 'bg-green-50 text-green-700 border-green-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
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

export default function ResultsPage({ result, onReset }: Props) {
  const { synthesis_report: r, assessment: a } = result
  const dim = a.fusion_summary.dimension_scores

  return (
    <div className="space-y-6">

      {/* Hero card — summary + decision */}
      <div className="card border-l-4 border-l-brand-500">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div className="flex-1">
            <p className="section-title">Executive Summary</p>
            <p className="text-slate-700 text-sm leading-relaxed">{r.executive_summary}</p>
          </div>
          <div className="flex flex-col items-start sm:items-end gap-2 shrink-0">
            <DecisionBadge decision={r.decision} />
            <ConfidenceBadge level={r.confidence_level} />
            <p className="text-xs text-slate-400">
              Score:{' '}
              <span className="font-mono font-semibold text-slate-600">
                {Math.round(r.overall_score * 100)}/100
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* Pipeline steps confirmation */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(result.pipeline_steps).map(([key, done]) => (
          <span key={key} className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium
            ${done ? 'bg-green-50 border-green-200 text-green-700' : 'bg-slate-50 border-slate-200 text-slate-400'}`}>
            {done ? '✓' : '○'} {key.replace(/_/g, ' ')}
          </span>
        ))}
      </div>

      {/* Dimension scores */}
      <div className="card">
        <p className="section-title">Dimension scores
          <span className="ml-2 font-normal normal-case text-slate-400 text-xs">
            CV 35% · Tests 40% · Interview 25%
          </span>
        </p>
        <div className="space-y-3">
          {[
            { label: 'Technical fit', value: dim.technical_fit },
            { label: 'Motivation fit', value: dim.motivation_fit },
            { label: 'Communication fit', value: dim.communication_fit },
            { label: 'Overall score', value: dim.overall_score },
          ].map(({ label, value }) => (
            <div key={label}>
              <div className="flex justify-between mb-1">
                <span className="text-xs text-slate-600 font-medium">{label}</span>
              </div>
              <ScoreBar value={value} color={value >= 0.7 ? 'green' : value >= 0.5 ? 'brand' : 'amber'} />
            </div>
          ))}
        </div>
      </div>

      {/* Strengths / Weaknesses / Risks */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card">
          <p className="section-title text-green-600">Strengths</p>
          <TagList items={r.strengths} variant="green" />
        </div>
        <div className="card">
          <p className="section-title text-red-500">Weaknesses</p>
          <TagList items={r.weaknesses} variant="red" />
        </div>
        <div className="card">
          <p className="section-title text-amber-500">Risk factors</p>
          <TagList items={r.risks} variant="amber" />
        </div>
      </div>

      {/* CV matching detail */}
      <div className="card">
        <p className="section-title">CV / Profile matching
          <span className="ml-2 font-normal normal-case text-slate-400">
            HrFlow score: {a.cv_profile_matching.score.toFixed(0)}/100 · experience fit: {a.cv_profile_matching.experience_fit}
          </span>
        </p>
        <p className="text-sm text-slate-600 mb-3">{a.cv_profile_matching.summary}</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-medium text-green-600 mb-1.5">Matched skills</p>
            <TagList items={a.cv_profile_matching.matched_skills} variant="green" />
          </div>
          <div>
            <p className="text-xs font-medium text-red-500 mb-1.5">Missing skills</p>
            <TagList items={a.cv_profile_matching.missing_skills} variant="red" />
          </div>
        </div>
      </div>

      {/* Test assessment */}
      <div className="card">
        <p className="section-title">Test assessment</p>
        <p className="text-sm text-slate-600 mb-4">{a.test_assessment.summary}</p>
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Technical', value: a.test_assessment.aggregated_scores.technical_score, max: 5 },
            { label: 'Soft skills', value: a.test_assessment.aggregated_scores.soft_skills_score, max: 5 },
            { label: 'Motivation', value: a.test_assessment.aggregated_scores.motivation_score, max: 5 },
          ].map(({ label, value, max }) => (
            <div key={label} className="text-center p-3 rounded-lg bg-slate-50">
              <p className="text-2xl font-bold text-slate-700">{value.toFixed(1)}</p>
              <p className="text-xs text-slate-400">/ {max}</p>
              <p className="text-xs font-medium text-slate-500 mt-1">{label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Technical & behavioral assessments */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="card">
          <p className="section-title">Technical assessment</p>
          <p className="text-sm text-slate-600 leading-relaxed">{r.technical_assessment}</p>
        </div>
        <div className="card">
          <p className="section-title">Behavioral & motivation</p>
          <p className="text-sm text-slate-600 leading-relaxed">{r.behavioral_assessment}</p>
        </div>
      </div>

      {/* Interview signals */}
      <div className="card">
        <p className="section-title">Interview signals
          <span className="ml-2 font-normal normal-case text-slate-400">
            {a.interview_assessment.interview_type.replace(/_/g, ' ')} ·
            motivation: <span className="font-medium">{a.interview_assessment.extracted_signals.motivation_signal}</span> ·
            psychological: <span className="font-medium">{a.interview_assessment.extracted_signals.psychological_signal}</span>
          </span>
        </p>
        <p className="text-sm text-slate-600 mb-4">{a.interview_assessment.summary}</p>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs font-medium text-green-600 mb-1.5">Strengths</p>
            <TagList items={a.interview_assessment.extracted_signals.strengths} variant="green" />
          </div>
          <div>
            <p className="text-xs font-medium text-red-500 mb-1.5">Weaknesses</p>
            <TagList items={a.interview_assessment.extracted_signals.weaknesses} variant="red" />
          </div>
          <div>
            <p className="text-xs font-medium text-amber-500 mb-1.5">Risks</p>
            <TagList items={a.interview_assessment.extracted_signals.risks} variant="amber" />
          </div>
        </div>
      </div>

      {/* Consistency analysis */}
      <div className="card">
        <p className="section-title">Consistency analysis</p>
        <p className="text-sm text-slate-600 mb-3">{r.consistency_analysis}</p>
        <div className="space-y-1.5">
          {a.fusion_summary.consistency_flags.map((flag, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-slate-600">
              <span className="mt-0.5 text-blue-400">◆</span>
              {flag}
            </div>
          ))}
        </div>
      </div>

      {/* Final justification */}
      <div className="card bg-slate-50 border-slate-200">
        <p className="section-title">Final justification</p>
        <p className="text-sm text-slate-700 leading-relaxed">{r.justification}</p>
      </div>

      {/* Actions */}
      <div className="flex justify-between items-center pt-2 pb-8">
        <button onClick={onReset} className="btn-ghost">
          ← Evaluate another candidate
        </button>
        <button
          onClick={() => window.print()}
          className="btn-ghost text-slate-500">
          🖨 Print / Export
        </button>
      </div>
    </div>
  )
}
