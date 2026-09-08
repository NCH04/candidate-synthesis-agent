#!/usr/bin/env python3
"""Capture the four pipeline screens for the README / portfolio posts.

Walks the demo-mode flow end to end in headless Chromium and writes retina-
resolution PNGs to docs/screenshots/.

    pip install playwright && playwright install chromium
    DEMO_MODE=true STATIC_DIR=$PWD/frontend/dist \
        uvicorn main:app --app-dir backend --port 8000 &
    python scripts/screenshots.py

Options:
    --url        base URL of a running instance (default http://localhost:8000)
    --out        output directory (default docs/screenshots)
    --width      viewport width in CSS pixels (default 1440)
    --scale      device pixel ratio; 2 gives retina-sharp images (default 2)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

# The prepare request is a single fast call in demo mode, so the processing
# screen would flash past. Holding the response briefly makes it capturable
# without touching application code.
PREPARE_DELAY_MS = 2500


def _shot(page, out_dir: Path, name: str, *, full_page: bool = False) -> None:
    path = out_dir / name
    page.screenshot(path=str(path), full_page=full_page)
    print(f"  ✓ {path}")


def capture(base_url: str, out_dir: Path, width: int, scale: int) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": width, "height": 900},
            device_scale_factor=scale,
        )
        page = context.new_page()

        page.route(
            "**/api/candidate/pipeline/prepare",
            lambda route: (page.wait_for_timeout(PREPARE_DELAY_MS), route.continue_())[-1],
        )

        try:
            page.goto(base_url, wait_until="networkidle", timeout=20_000)
        except PlaywrightTimeout:
            print(f"error: no app answering at {base_url}", file=sys.stderr)
            browser.close()
            return 1

        # 1 — input form, with the demo banner
        page.wait_for_selector("text=Target job", timeout=10_000)
        print("Capturing…")
        _shot(page, out_dir, "1-input.png", full_page=True)

        demo_button = page.get_by_role("button", name="Run sample evaluation")
        if not demo_button.count():
            print(
                "error: demo button missing — start the server with DEMO_MODE=true",
                file=sys.stderr,
            )
            browser.close()
            return 1
        demo_button.click()

        # 2 — processing (prepare phase)
        page.wait_for_selector("text=Building candidate assessment", timeout=10_000)
        page.wait_for_timeout(600)
        _shot(page, out_dir, "2-processing.png")

        # 3 — live synthesis stream, caught mid-flight
        page.wait_for_selector("text=Live stream", timeout=20_000)
        page.wait_for_timeout(1200)
        _shot(page, out_dir, "3-streaming.png")

        # 4 — final report
        page.wait_for_selector("text=Recommended next steps", timeout=40_000)
        page.wait_for_timeout(400)
        _shot(page, out_dir, "4-results-full.png", full_page=True)
        # Above-the-fold crop: the decision + score block, best single image for a post.
        _shot(page, out_dir, "5-results-hero.png")

        browser.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--out", default="docs/screenshots", type=Path)
    ap.add_argument("--width", default=1440, type=int)
    ap.add_argument("--scale", default=2, type=int)
    args = ap.parse_args()
    return capture(args.url, args.out, args.width, args.scale)


if __name__ == "__main__":
    raise SystemExit(main())
