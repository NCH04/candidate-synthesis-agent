#!/usr/bin/env bash
#
# Build the static demo bundle: the React app with the backend's canned demo
# responses embedded, so it runs with no server at all.
#
# The public demo has always served pre-computed results (DEMO_MODE=true never
# calls Claude). Hugging Face now bills Spaces that run compute, so the same
# responses are served from the browser instead — same output, free to host,
# no cold start. The real backend is unchanged and still runs locally and under
# Docker.
#
# Output: frontend/dist-static/
#
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

GENERATED="frontend/src/generated"
OUT="dist-static"

die() { printf 'error: %s\n' "$1" >&2; exit 1; }

[ -f backend/demo_data/sample.json ] || die "missing backend/demo_data/sample.json"
[ -f backend/jobs.json ] || die "missing backend/jobs.json"
command -v npm >/dev/null || die "npm is required"

# The backend fixtures stay the single source of truth; these are build-time
# copies (gitignored) so Vite can bundle them.
echo "Copying backend fixtures into the bundle…"
mkdir -p "$GENERATED"
cp backend/demo_data/sample.json "$GENERATED/demo-sample.json"
cp backend/jobs.json "$GENERATED/jobs.json"

echo "Building…"
(cd frontend && npm run build:static -- --outDir "$OUT" --emptyOutDir)

[ -f "frontend/$OUT/index.html" ] || die "build produced no index.html"
echo "  ✓ frontend/$OUT ($(du -sh "frontend/$OUT" | cut -f1))"
