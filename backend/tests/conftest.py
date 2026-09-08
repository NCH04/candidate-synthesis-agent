"""Shared test setup.

Every test runs in DEMO_MODE so the suite never needs an Anthropic key and
never spends API budget. The pure services (fusion, parser, fairness) are
tested directly and involve no network at all.
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Must be set before `main` is imported — it reads them at module scope.
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("APP_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    import main  # noqa: E402

    with TestClient(main.app) as c:
        yield c
