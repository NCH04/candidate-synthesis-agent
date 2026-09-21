#!/usr/bin/env bash
#
# Build the static demo and publish it to a Hugging Face Static Space.
#
# Why static
# ----------
# Hugging Face bills Spaces that run compute (Docker, Gradio); Static Spaces
# stay free. The public demo has always served pre-computed results anyway —
# DEMO_MODE=true never calls Claude — so the same canned responses are answered
# in the browser instead. Same output, free to host, no cold start.
#
# The real backend is unchanged: it still runs locally and under Docker, and
# deploys to any container host (see README §4.2).
#
# How it works
# ------------
# The Space is published from a throwaway git repository in a temp directory:
# nothing is branched, checked out or committed in your working repo, so a
# failed run cannot leave artefacts behind or strand you on the wrong branch.
#
# One-time setup
# --------------
#   1. Create a Static Space at https://huggingface.co/new-space
#        SDK: Static   Visibility: Public
#   2. git remote add space https://huggingface.co/spaces/<hf-user>/<space-name>
#
# Usage
# -----
#   ./scripts/sync-space.sh              # build and publish
#   ./scripts/sync-space.sh --no-push    # build and stage locally, inspect first
#
set -euo pipefail

SPACE_REMOTE="${SPACE_REMOTE:-space}"
PUSH=1
[ "${1:-}" = "--no-push" ] && PUSH=0

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

SPACE_README="deploy/hf-space-readme.md"
BUNDLE="frontend/dist-static"

die() { printf 'error: %s\n' "$1" >&2; exit 1; }

[ -f "$SPACE_README" ] || die "missing $SPACE_README"

REMOTE_URL=""
HF_OWNER=""
if [ "$PUSH" -eq 1 ]; then
    git remote get-url "$SPACE_REMOTE" >/dev/null 2>&1 || die \
"remote '$SPACE_REMOTE' is not configured. Run:
  git remote add $SPACE_REMOTE https://huggingface.co/spaces/<hf-user>/<space-name>
Or build without publishing:
  $0 --no-push"

    REMOTE_URL="$(git remote get-url "$SPACE_REMOTE")"

    # A Space URL built from a GitHub username instead of a Hugging Face one
    # fails later with an opaque 'not found'. Catch it here.
    case "$REMOTE_URL" in
        *huggingface.co/spaces/*)
            HF_OWNER="${REMOTE_URL#*huggingface.co/spaces/}"
            HF_OWNER="${HF_OWNER%%/*}"
            if command -v curl >/dev/null 2>&1; then
                status="$(curl -s -o /dev/null -w '%{http_code}' \
                    "https://huggingface.co/api/users/$HF_OWNER/overview" || echo 000)"
                [ "$status" = "404" ] && die \
"'$HF_OWNER' is not a Hugging Face account (your GitHub username is not
necessarily your HF one). Check it at https://huggingface.co/settings/profile
then fix the remote:
  git remote set-url $SPACE_REMOTE https://huggingface.co/spaces/<hf-user>/<space-name>"
            fi
            ;;
        *) die "remote '$SPACE_REMOTE' is not a Hugging Face Space URL: $REMOTE_URL" ;;
    esac
fi

./scripts/build-static-demo.sh
[ -f "$BUNDLE/index.html" ] || die "no bundle at $BUNDLE"

# Assemble the Space in a throwaway repo, entirely outside this one.
STAGE="$(mktemp -d)"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

cp -r "$BUNDLE/." "$STAGE/"
cp "$SPACE_README" "$STAGE/README.md"

git -C "$STAGE" init -q -b main
git -C "$STAGE" add -A
git -C "$STAGE" -c user.name="$(git config user.name || echo deploy)" \
                -c user.email="$(git config user.email || echo deploy@localhost)" \
                commit -q -m "Publish static demo"

echo "  ✓ staged $(du -sh "$STAGE" | cut -f1) in $STAGE"

if [ "$PUSH" -eq 0 ]; then
    KEEP="$REPO_ROOT/$BUNDLE"
    echo "  → not published. The bundle is at $KEEP"
    echo "    Preview it with:  python3 -m http.server -d $KEEP 8010"
    exit 0
fi

echo "Publishing to '$SPACE_REMOTE' ($REMOTE_URL)…"
PUSH_LOG="$(mktemp)"
if git -C "$STAGE" push --force "$REMOTE_URL" main 2>&1 | tee "$PUSH_LOG"; then
    rm -f "$PUSH_LOG"
    echo "  ✓ published — the Space will rebuild automatically"
    echo "    https://huggingface.co/spaces/$HF_OWNER/${REMOTE_URL##*/}"
else
    # Report the failure that actually happened: leading with token instructions
    # when the Space simply does not exist sends people chasing the wrong problem.
    if grep -qiE "not found|does not exist|404" "$PUSH_LOG"; then
        rm -f "$PUSH_LOG"
        die "the Space was not found. git cannot create it for you.

If it does not exist yet, create it at https://huggingface.co/new-space
  Owner : $HF_OWNER
  Name  : ${REMOTE_URL##*/}
  SDK   : Static      <-- not Docker: Docker Spaces are a paid plan
  Visibility: Public

If it already exists, Hugging Face also answers 'not found' when your token
cannot write to it — check the token has WRITE access and belongs to
'$HF_OWNER': https://huggingface.co/settings/tokens"
    fi
    rm -f "$PUSH_LOG"
    die "push failed — authentication.

Hugging Face dropped git password authentication. Use a User Access Token:
  1. Create one with WRITE access at https://huggingface.co/settings/tokens
  2. Push again — enter your HF username, and paste the TOKEN as the password
     (\`git config --global credential.helper store\` saves it for next time)"
fi
