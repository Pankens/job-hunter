from __future__ import annotations

from pathlib import Path

import scripts.export_jobs as exporter


ROOT = Path(__file__).resolve().parents[1]


def test_no_mock_fallback_when_use_mock_false(monkeypatch):
    config = {
        "use_mock": False,
        "sources": {"infojobs_html": True},
        "locations": ["Valencia"],
        "general_queries": ["dependiente"],
        "technical_queries": [],
    }

    def no_jobs(_config):
        return [], {
            "generatedAt": "2026-07-08T00:00:00Z",
            "runMode": "test",
            "mockEnabled": False,
            "activeSources": ["infojobs_html"],
            "queriesCount": 1,
            "rawTotalBeforeSourceDedup": 0,
            "rawTotal": 0,
            "sourceReports": {"infojobs_html": {"rawJobs": 0, "errors": [], "logs": []}},
        }

    monkeypatch.setattr(exporter, "collect_real_sources", no_jobs)
    raw_jobs, report = exporter.load_raw_jobs(config, "2026-07-08T00:00:00Z")

    assert raw_jobs == []
    assert report["mockFallbackUsed"] is False
    assert "No se obtuvieron ofertas reales" in report["error"]


def test_mock_fallback_only_when_use_mock_true(monkeypatch):
    config = {
        "use_mock": True,
        "sources": {"infojobs_html": True},
        "locations": ["Valencia"],
        "general_queries": ["dependiente"],
        "technical_queries": [],
    }

    def no_jobs(_config):
        return [], {
            "generatedAt": "2026-07-08T00:00:00Z",
            "runMode": "test",
            "mockEnabled": True,
            "activeSources": ["infojobs_html"],
            "queriesCount": 1,
            "rawTotalBeforeSourceDedup": 0,
            "rawTotal": 0,
            "sourceReports": {},
        }

    monkeypatch.setattr(exporter, "collect_real_sources", no_jobs)
    raw_jobs, report = exporter.load_raw_jobs(config, "2026-07-08T00:00:00Z")

    assert raw_jobs
    assert report["mockFallbackUsed"] is True
    assert report["mockFallbackReason"]
