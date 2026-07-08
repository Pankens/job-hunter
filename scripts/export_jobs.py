"""Genera el JSON estático desde collectors HTML públicos o mock explícito."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.collect_sources import collect_real_sources, write_report
from scripts.deduplicate import deduplicate_jobs
from scripts.filter_jobs import filter_jobs
from scripts.normalize import normalize_jobs

MOCK_INPUT = ROOT / "data" / "mock" / "source_jobs.json"
RULES_INPUT = ROOT / "config" / "filter_rules.json"
SOURCES_INPUT = ROOT / "config" / "sources.json"
OUTPUT = ROOT / "web" / "src" / "data" / "jobs.json"
REPORT_OUTPUT = ROOT / "data" / "last_run_report.json"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _empty_report(config: dict[str, Any], generated_at: str, error: str) -> dict[str, Any]:
    return {
        "generatedAt": generated_at,
        "runMode": "local",
        "mockEnabled": bool(config.get("use_mock", False)),
        "activeSources": [
            name for name, enabled in config.get("sources", {}).items() if enabled
        ],
        "queriesCount": 0,
        "rawTotalBeforeSourceDedup": 0,
        "rawTotal": 0,
        "sourceReports": {},
        "error": error,
    }


def load_raw_jobs(config: dict[str, Any], generated_at: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Carga fuentes reales. Mock solo existe en modo explícito de desarrollo."""
    try:
        raw_jobs, report = collect_real_sources(config)
    except Exception as error:
        report = _empty_report(config, generated_at, repr(error))
        raw_jobs = []
        print(f"ERROR GLOBAL DEL COLLECTOR: {error!r}")

    if raw_jobs:
        return raw_jobs, report

    if config.get("use_mock"):
        print("USANDO MOCK FALLBACK")
        report["mockFallbackUsed"] = True
        report["mockFallbackReason"] = "No se obtuvieron ofertas reales y use_mock=true"
        return read_json(MOCK_INPUT), report

    report["mockFallbackUsed"] = False
    report["error"] = report.get("error") or "No se obtuvieron ofertas reales de fuentes públicas"
    return [], report


def export_jobs() -> dict[str, Any]:
    generated_at_dt = datetime.now(timezone.utc).replace(microsecond=0)
    generated_at = generated_at_dt.isoformat().replace("+00:00", "Z")
    rules = read_json(RULES_INPUT)
    sources_config = read_json(SOURCES_INPUT)
    raw_jobs, last_run_report = load_raw_jobs(sources_config, generated_at)

    normalized = normalize_jobs(raw_jobs, generated_at_dt)
    unique = deduplicate_jobs(
        normalized,
        description_similarity_threshold=rules["deduplication"][
            "description_similarity_threshold"
        ],
    )
    jobs = filter_jobs(unique, rules)
    jobs.sort(key=lambda job: job["publishedAt"], reverse=True)

    valid_count = sum(job["valid"] for job in jobs)
    discarded_count = sum(not job["valid"] for job in jobs)
    source_counts = {
        name: report.get("rawJobs", 0)
        for name, report in last_run_report.get("sourceReports", {}).items()
    }
    last_run_report.update(
        {
            "generatedAt": generated_at,
            "normalized": len(normalized),
            "deduplicated": len(unique),
            "valid": valid_count,
            "discarded": discarded_count,
            "sourceCounts": source_counts,
        }
    )

    mode = "mock-fallback" if last_run_report.get("mockFallbackUsed") else "live"
    if not jobs and not last_run_report.get("mockFallbackUsed"):
        mode = "empty-real-run"

    payload = {
        "schemaVersion": 3,
        "generatedAt": generated_at,
        "mode": mode,
        "isMock": bool(last_run_report.get("mockFallbackUsed", False)),
        "hasRealData": bool(raw_jobs) and not last_run_report.get("mockFallbackUsed", False),
        "emptyReason": None if jobs else last_run_report.get("error"),
        "lastRunReport": last_run_report,
        "summary": {
            "input": len(raw_jobs),
            "total": len(jobs),
            "duplicatesRemoved": len(normalized) - len(unique),
            "valid": valid_count,
            "discarded": discarded_count,
        },
        "jobs": jobs,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    write_report(REPORT_OUTPUT, last_run_report)
    return payload


if __name__ == "__main__":
    result = export_jobs()
    report = result["lastRunReport"]
    summary = result["summary"]
    print(f"Número normalizadas: {report['normalized']}")
    print(f"Número deduplicadas: {report['deduplicated']}")
    print(f"Número válidas: {summary['valid']}")
    print(f"Número descartadas: {summary['discarded']}")
    if result["isMock"]:
        print("USANDO MOCK FALLBACK")
    if result["mode"] == "empty-real-run":
        print(f"SIN OFERTAS REALES: {result['emptyReason']}")
    for source, count in report.get("sourceCounts", {}).items():
        print(f"Resumen fuente {source}: {count} ofertas raw")
    print(f"Exportación {result['mode']} completada -> {OUTPUT.relative_to(ROOT)}")
    print(f"Reporte de ejecución -> {REPORT_OUTPUT.relative_to(ROOT)}")
