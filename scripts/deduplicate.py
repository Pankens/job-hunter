"""Eliminación de ofertas repetidas."""

from __future__ import annotations

import hashlib
from typing import Any

from scripts.normalize import comparable_text


def _fingerprint(job: dict[str, Any]) -> str:
    content = "|".join(
        [
            comparable_text(job.get("title")),
            comparable_text(job.get("company")),
            comparable_text(job.get("city")),
        ]
    )
    return hashlib.sha1(content.encode()).hexdigest()


def deduplicate_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_ids: set[str] = set()
    seen_content: set[str] = set()
    unique: list[dict[str, Any]] = []

    for job in jobs:
        source_key = f"{job.get('source')}:{job.get('sourceId')}"
        fingerprint = _fingerprint(job)
        if source_key in seen_ids or fingerprint in seen_content:
            continue
        seen_ids.add(source_key)
        seen_content.add(fingerprint)
        unique.append(job)

    return unique
