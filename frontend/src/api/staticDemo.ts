/**
 * Browser-side stand-in for the backend, used by the static demo build only.
 *
 * The public demo has always served pre-computed results: with `DEMO_MODE=true`
 * the FastAPI backend answers every route from `backend/demo_data/sample.json`
 * and never calls Claude. Hugging Face now bills Spaces that run compute, so
 * the same canned responses are served from the browser instead — visually
 * identical, free to host, and with no cold start.
 *
 * This module is bundled only when VITE_STATIC_DEMO=true; Vite inlines the flag
 * so the branch and its JSON payload are dropped from the normal build.
 *
 * The real backend is unchanged and still runs locally and under Docker.
 */
import jobs from '../generated/jobs.json'
import sample from '../generated/demo-sample.json'

const encoder = new TextEncoder()

/** Matches backend/services/demo_service.py: 24-char chunks, 20 ms apart. */
const STREAM_CHUNK = 24
const STREAM_DELAY_MS = 20
/** Stand-ins for the critic and fairness passes, which take real time server-side. */
const CRITIC_MS = 900
const FAIRNESS_MS = 600

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** Replays the synthesis as a real SSE stream so StreamingPage is untouched. */
function synthesisStream(): Response {
  const report = sample.synthesis_report
  const text = JSON.stringify(report, null, 2)

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (event: string, data: unknown) =>
        controller.enqueue(
          encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`),
        )

      try {
        send('phase', { phase: 'draft' })
        for (let i = 0; i < text.length; i += STREAM_CHUNK) {
          send('delta', { text: text.slice(i, i + STREAM_CHUNK) })
          await sleep(STREAM_DELAY_MS)
        }

        send('phase', { phase: 'critic' })
        await sleep(CRITIC_MS)

        send('phase', { phase: 'fairness' })
        await sleep(FAIRNESS_MS)

        send('phase', { phase: 'done' })
        send('final', report)
      } finally {
        controller.close()
      }
    },
  })

  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

const ROUTES: Record<string, () => Response> = {
  '/api/config': () =>
    jsonResponse({
      demo_mode: true,
      economy_mode: false,
      models: { fast: 'claude-haiku-4-5', smart: 'claude-sonnet-5' },
    }),
  '/api/jobs/list': () => jsonResponse({ jobs }),
  '/api/cv/parse': () => jsonResponse(sample.cv_parse),
  '/api/test/parse': () => jsonResponse(sample.test_parse),
  '/api/candidate/pipeline/prepare': () => jsonResponse({ assessment: sample.assessment }),
  '/api/candidate/synthesis/stream': synthesisStream,
  '/api/candidate/synthesis/generate': () => jsonResponse(sample.synthesis_report),
}

function pathOf(input: RequestInfo | URL): string {
  const raw =
    typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
  try {
    return new URL(raw, window.location.href).pathname
  } catch {
    return raw
  }
}

/** Route /api/* to the canned responses; everything else hits the network. */
export function installStaticDemo(): void {
  const realFetch = window.fetch.bind(window)

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const handler = ROUTES[pathOf(input)]
    if (handler) {
      // A touch of latency so the loading states are visible, as they are
      // against the real backend.
      await sleep(250)
      return handler()
    }
    return realFetch(input, init)
  }
}
