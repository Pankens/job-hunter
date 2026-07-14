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
            "description": (
                "Gestion de documentacion, atencion al cliente, archivo de contratos "
                "y coordinacion diaria con el equipo administrativo."
            ),
            "requirements": "Organizacion y manejo de herramientas ofimaticas.",
            "salary_text": "1.300 EUR brutos/mes",
            "salary_base_eur_month": 1300,
            "has_commission": False,
            "published_at": "2026-07-01T00:00:00Z",
            "url": "https://example.test/job/test-job",
            "direct_url": True,
        }
        raw.update(overrides)
        return normalize_job(raw, datetime(2026, 7, 1, tzinfo=timezone.utc))

    return factory
