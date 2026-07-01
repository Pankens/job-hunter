from __future__ import annotations

import json
from pathlib import Path

import scripts.export_jobs as exporter
from scripts.sources.infojobs import InfoJobsSourceError


ROOT = Path(__file__).resolve().parents[1]


def test_falls_back_to_mock_when_infojobs_fails(monkeypatch):
    searches = json.loads((ROOT / "config" / "searches.json").read_text(encoding="utf-8"))

    def fail(_settings):
        raise InfoJobsSourceError("timeout de prueba")

    monkeypatch.setattr(exporter, "fetch_infojobs_jobs", fail)
    raw_jobs, status = exporter.load_raw_jobs(searches)

    assert raw_jobs
    assert status == {
        "requested": "infojobs",
        "used": "mock",
        "fallback": True,
        "warning": "timeout de prueba",
    }
