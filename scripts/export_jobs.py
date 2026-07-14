"""Generate the static jobs JSON from real public sources only."""

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

RULES_INPUT = ROOT / "config" / "filter_rules.json"
SOURCES_INPUT = ROOT / "config" / "sources.json"
OUTPUT = ROOT / "web" / "src" / "data" / "jobs.json"
REPORT_OUTPUT = ROOT / "data" / "last_run_report.json"
SOURCE_HEALTH_OUTPUT = ROOT / "data" / "source-health.json"


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
    """Load real sources. Mocks are never published."""
    try:
        raw_jobs, report = collect_real_sources(config)
    except Exception as error:
        report = _empty_report(config, generated_at, repr(error))
        raw_jobs = []
        print(f"ERROR GLOBAL DEL COLLECTOR: {error!r}")

    if raw_jobs:
        return raw_jobs, report

    report["mockFallbackUsed"] = False
    if config.get("use_mock"):
        report["mockDisabledReason"] = "Los mocks estan desactivados para publicacion"
    report["error"] = report.get("error") or "No se obtuvieron ofertas reales de fuentes publicas"
    return [], report


def build_source_health(report: dict[str, Any], generated_at: str) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for name, source_report in report.get("sourceReports", {}).items():
        errors = source_report.get("errors", [])
        raw_jobs = int(source_report.get("rawJobs", 0) or 0)
        sources[name] = {
            "ok": raw_jobs > 0 and not errors,
            "rawJobs": raw_jobs,
            "errors": errors,
            "skipped": bool(source_report.get("skipped", False)),
            "skipReason": source_report.get("skipReason"),
        }
    return {
        "generatedAt": generated_at,
        "activeSources": report.get("activeSources", []),
        "sources": sources,
    }


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
    jobs.sort(key=lambda job: job.get("publishedAt") or job.get("firstSeenAt") or "", reverse=True)

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

    mode = "live" if jobs else "empty-real-run"
    source_health = build_source_health(last_run_report, generated_at)

    payload = {
        "schemaVersion": 4,
        "generatedAt": generated_at,
        "mode": mode,
        "isMock": False,
        "hasRealData": bool(raw_jobs),
        "emptyReason": None if jobs else last_run_report.get("error"),
        "lastRunReport": last_run_report,
        "sourceHealth": source_health,
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
    write_report(SOURCE_HEALTH_OUTPUT, source_health)
    return payload


if __name__ == "__main__":
    result = export_jobs()
    report = result["lastRunReport"]
    summary = result["summary"]
    print(f"Numero normalizadas: {report['normalized']}")
    print(f"Numero deduplicadas: {report['deduplicated']}")
    print(f"Numero validas: {summary['valid']}")
    print(f"Numero descartadas: {summary['discarded']}")
    if result["mode"] == "empty-real-run":
        print(f"SIN OFERTAS REALES: {result['emptyReason']}")
    for source, count in report.get("sourceCounts", {}).items():
        print(f"Resumen fuente {source}: {count} ofertas raw")
    print(f"Exportacion {result['mode']} completada -> {OUTPUT.relative_to(ROOT)}")
    print(f"Reporte de ejecucion -> {REPORT_OUTPUT.relative_to(ROOT)}")
    print(f"Salud de fuentes -> {SOURCE_HEALTH_OUTPUT.relative_to(ROOT)}")
