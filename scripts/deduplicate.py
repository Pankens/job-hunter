"""Eliminación de ofertas repetidas por identidad y similitud de contenido."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from scripts.normalize import comparable_text


def _identity(job: dict[str, Any]) -> tuple[str, str, str]:
    return (
        comparable_text(job.get("title")),
        comparable_text(job.get("company")),
        comparable_text(job.get("city")),
    )


def _description_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_text = comparable_text(left.get("description"))
    right_text = comparable_text(right.get("description"))
    if not left_text and not right_text:
        return 1.0
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def deduplicate_jobs(
    jobs: list[dict[str, Any]], description_similarity_threshold: float = 0.82
) -> list[dict[str, Any]]:
    """
    Conserva la primera aparición.

    Dos ofertas son duplicadas si comparten fuente/id, o si tienen el mismo título,
    empresa y ciudad y sus descripciones alcanzan el umbral de similitud configurado.
    """
    seen_source_ids: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []

    for job in jobs:
        source_id = (
            comparable_text(job.get("source")),
            comparable_text(job.get("sourceId", job.get("source_id"))),
        )
        if source_id[1] and source_id in seen_source_ids:
            continue

        duplicate = any(
            _identity(job) == _identity(existing)
            and _description_similarity(job, existing) >= description_similarity_threshold
            for existing in unique
        )
        if duplicate:
            continue

        if source_id[1]:
            seen_source_ids.add(source_id)
        unique.append(job)

    return unique
