from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts.normalize import normalize_job


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def rules() -> dict[str, Any]:
    with (ROOT / "config" / "filter_rules.json").open(encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture
def make_job():
    def factory(**overrides: Any) -> dict[str, Any]:
        raw = {
            "source": "infojobs",
            "source_id": "test-job",
            "title": "Auxiliar administrativo/a",
            "company": "Empresa de prueba",
            "city": "Valencia",
            "location": "Valencia capital",
            "description": "Gestión de documentación y atención al cliente.",
            "requirements": "Organización y manejo de herramientas ofimáticas.",
            "salary_text": "1.300 € brutos/mes",
            "salary_base_eur_month": 1300,
            "has_commission": False,
            "published_hours_ago": 2,
            "url": "https://example.test/job",
        }
        raw.update(overrides)
        return normalize_job(raw, datetime(2026, 7, 1, tzinfo=timezone.utc))

    return factory
