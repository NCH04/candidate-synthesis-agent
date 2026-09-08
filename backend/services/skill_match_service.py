"""
Semantic skill matching via sentence-transformers (local model, no API key).

Replaces exact-string matching: "py3" now matches "Python",
"ReactJS" matches "React", "k8s" matches "Kubernetes", etc.

Model: all-MiniLM-L6-v2 (~80 MB, downloaded once on first run).
Inference is fast (~10ms per skill on CPU).

`sentence_transformers` (and the ~2 GB torch stack behind it) is imported
lazily inside `_get_model`, not at module import. That keeps the pure-logic
services importable — and the test suite and CI runnable — without installing
torch at all.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_DEFAULT_THRESHOLD = 0.55  # cosine similarity above this counts as a match

_model: SentenceTransformer | None = None
_model_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    """Lazy-load the embedding model (and the torch stack). Thread-safe."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _normalize(text: str) -> str:
    return text.strip().lower()


@lru_cache(maxsize=4096)
def _embed_cached(text: str) -> tuple[float, ...]:
    """Cache embeddings per-string. Returns tuple for hashability."""
    vec = _get_model().encode(text, normalize_embeddings=True)
    return tuple(float(x) for x in vec)


def _embed_batch(texts: list[str]) -> np.ndarray:
    """Embed a list of texts, hitting the cache where possible."""
    return np.array([list(_embed_cached(_normalize(t))) for t in texts])


def match_skills(
    candidate_skills: list[str],
    target_skills: list[str],
    threshold: float = _DEFAULT_THRESHOLD,
) -> dict[str, list[str]]:
    """
    Match candidate skills against target (required) skills via cosine similarity.

    Returns:
        {
          "matched":  ["Python", "FastAPI"],   # target skills the candidate covers
          "missing":  ["Kubernetes"],          # target skills the candidate lacks
          "extra":    ["GraphQL"]              # candidate skills not asked for
        }
    """
    if not target_skills:
        return {"matched": [], "missing": [], "extra": list(candidate_skills)}
    if not candidate_skills:
        return {"matched": [], "missing": list(target_skills), "extra": []}

    cand_emb = _embed_batch(candidate_skills)
    targ_emb = _embed_batch(target_skills)

    # Cosine similarity matrix: rows=targets, cols=candidates
    sims = targ_emb @ cand_emb.T

    matched_targets: list[str] = []
    missing_targets: list[str] = []
    matched_cand_idx: set[int] = set()

    for t_idx, target in enumerate(target_skills):
        best_cand = int(np.argmax(sims[t_idx]))
        best_score = float(sims[t_idx][best_cand])
        if best_score >= threshold:
            matched_targets.append(target)
            matched_cand_idx.add(best_cand)
        else:
            missing_targets.append(target)

    extra = [s for i, s in enumerate(candidate_skills) if i not in matched_cand_idx]

    return {"matched": matched_targets, "missing": missing_targets, "extra": extra}


def coverage_score(candidate_skills: list[str], target_skills: list[str]) -> float:
    """Skill-coverage ratio (0-1): proportion of target skills covered semantically."""
    if not target_skills:
        return 0.0
    result = match_skills(candidate_skills, target_skills)
    return round(len(result["matched"]) / len(target_skills), 3)
