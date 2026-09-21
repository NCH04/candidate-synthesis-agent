Copies of `backend/demo_data/sample.json` and `backend/jobs.json`, refreshed by
`scripts/build-static-demo.sh`.

**These are committed on purpose.** `staticDemo.ts` imports them, and Rollup
resolves that import even in the dead branch of the normal build — so they must
exist for *every* build path, including the Docker frontend stage, which only
receives `frontend/` and can never see the backend.

The backend files remain the single source of truth. CI fails if these copies
drift; run `./scripts/build-static-demo.sh` and commit the result.
