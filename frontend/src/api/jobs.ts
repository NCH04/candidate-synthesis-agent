import { JobOption } from '../types'

export async function fetchJobs(): Promise<JobOption[]> {
  const res = await fetch('/api/jobs/list')
  if (!res.ok) return []
  const data = await res.json()
  return (data.jobs || []) as JobOption[]
}
