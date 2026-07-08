"""Genera el JSON estático desde InfoJobs RSS o desde el fallback mock."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.deduplicate import deduplicate_jobs
from scripts.filter_jobs import filter_jobs
from scripts.normalize import normalize_jobs
from scripts.sources.infojobs import InfoJobsSourceError, fetch_infojobs_jobs

MOCK_INPUT = ROOT / "data" / "mock" / "source_jobs.json"
RULES_INPUT = ROOT / "config" / "filter_rules.json"
SEARCHES_INPUT = ROOT / "config" / "searches.json"
OUTPUT = ROOT / "web" / "src" / "data" / "jobs.json"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _mock_status(requested: str, warning: str, *, fallback: bool) -> dict[str, Any]:
    return {
        "requested": requested,
        "requestedLabel": "InfoJobs RSS" if requested == "infojobs" else "Mock",
        "used": "mock",
        "sourceLabel": "Mock",
        "fallback": fallback,
        "warning": warning,
        "feedsConsulted": 0,
        "offersObtained": 0,
        "sourceErrors": [],
        "sourceLogs": [],
    }


def _fallback_status_from_error(error: InfoJobsSourceError) -> dict[str, Any]:
    stats = getattr(error, "stats", None)
    if stats is None:
        return _mock_status("infojobs", str(error), fallback=True)
    return {
        "requested": "infojobs",
        "requestedLabel": "InfoJobs RSS",
        "used": "mock",
        "sourceLabel": "Mock",
        "fallback": True,
        "warning": str(error),
        "feedsConsulted": stats.feeds_consulted,
        "offersObtained": stats.offers_obtained,
        "sourceErrors": stats.errors,
        "sourceLogs": stats.logs,
    }


def load_raw_jobs(searches: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Carga la fuente activa y degrada a mocks ante cualquier fallo recuperable."""
    infojobs = searches["sources"]["infojobs"]
    if infojobs.get("enabled") and "infojobs" in searches.get("active_sources", []):
        try:
            raw_jobs, stats = fetch_infojobs_jobs(infojobs)
            if not raw_jobs:
                raise InfoJobsSourceError(
                    "InfoJobs RSS no devolvió ofertas para las búsquedas configuradas"
                )
            return raw_jobs, {
                "requested": "infojobs",
                "requestedLabel": "InfoJobs RSS",
                "used": "infojobs",
                "sourceLabel": stats.source,
                "fallback": False,
                "warning": None,
                "feedsConsulted": stats.feeds_consulted,
                "offersObtained": stats.offers_obtained,
                "sourceErrors": stats.errors,
                "sourceLogs": stats.logs,
            }
        except InfoJobsSourceError as error:
            fallback = read_json(MOCK_INPUT)
            return fallback, _fallback_status_from_error(error)

    return read_json(MOCK_INPUT), _mock_status(
        "mock",
        "InfoJobs RSS está deshabilitado en config/searches.json",
        fallback=False,
    )


def export_jobs() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0)
    rules = read_json(RULES_INPUT)
    searches = read_json(SEARCHES_INPUT)
    raw_jobs, source_status = load_raw_jobs(searches)

    normalized = normalize_jobs(raw_jobs, generated_at)
    unique = deduplicate_jobs(
        normalized,
        description_similarity_threshold=rules["deduplication"][
            "description_similarity_threshold"
        ],
    )
    jobs = filter_jobs(unique, rules)
    jobs.sort(key=lambda job: job["publishedAt"], reverse=True)

    payload = {
        "schemaVersion": 2,
        "generatedAt": generated_at.isoformat().replace("+00:00", "Z"),
        "mode": "live" if source_status["used"] == "infojobs" else "mock-fallback",
        "sourceStatus": source_status,
        "summary": {
            "input": len(raw_jobs),
            "total": len(jobs),
            "duplicatesRemoved": len(normalized) - len(unique),
            "valid": sum(job["valid"] for job in jobs),
            "discarded": sum(not job["valid"] for job in jobs),
        },
        "jobs": jobs,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return payload


if __name__ == "__main__":
    result = export_jobs()
    status = result["sourceStatus"]
    summary = result["summary"]
    print(f"Fuente intentada: {status['requestedLabel']}")
    print(f"Fuente usada: {status['sourceLabel']}")
    print(f"Feeds consultados: {status['feedsConsulted']}")
    print(f"Ofertas obtenidas: {status['offersObtained']}")
    print(f"Ofertas válidas: {summary['valid']}")
    print(f"Ofertas descartadas: {summary['discarded']}")
    if status.get("sourceLogs"):
        print("URLs consultadas:")
        for entry in status["sourceLogs"]:
            preview = entry.get("preview", "")
            print(
                "- "
                f"{entry['url']} | "
                f"HTTP {entry['status']} | "
                f"{entry['responseBytes']} bytes | "
                f"RSS válido: {'sí' if entry['validFeed'] else 'no'} | "
                f"items: {entry['itemsParsed']} | "
                f"motivo: {entry.get('reason') or '-'} | "
                f"preview: {preview}"
            )
    if status["fallback"]:
        print(f"*** MOCK FALLBACK ACTIVADO *** {status['warning']}")
    else:
        print("Mock fallback: no")
    if status.get("sourceErrors"):
        print(f"Avisos de fuente: {len(status['sourceErrors'])}")
    print(f"Exportación {result['mode']} completada -> {OUTPUT.relative_to(ROOT)}")
