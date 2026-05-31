export interface AppConfig {
  demo_mode: boolean
  economy_mode: boolean
  models: { fast: string; smart: string }
}

const DEFAULT_CONFIG: AppConfig = {
  demo_mode: false,
  economy_mode: false,
  models: { fast: '', smart: '' },
}

export async function fetchConfig(): Promise<AppConfig> {
  try {
    const res = await fetch('/api/config')
    if (!res.ok) return DEFAULT_CONFIG
    return (await res.json()) as AppConfig
  } catch {
    return DEFAULT_CONFIG
  }
}
