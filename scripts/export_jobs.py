"""Genera el JSON estático desde InfoJobs o desde el fallback mock."""

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


def load_raw_jobs(searches: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Carga la fuente activa y degrada a mocks ante cualquier fallo recuperable."""
    infojobs = searches["sources"]["infojobs"]
    if infojobs.get("enabled") and "infojobs" in searches.get("active_sources", []):
        try:
            raw_jobs = fetch_infojobs_jobs(infojobs)
            if not raw_jobs:
                raise InfoJobsSourceError("InfoJobs no devolvió ofertas para las búsquedas configuradas")
            return raw_jobs, {
                "requested": "infojobs",
                "used": "infojobs",
                "fallback": False,
                "warning": None,
            }
        except InfoJobsSourceError as error:
            fallback = read_json(MOCK_INPUT)
            return fallback, {
                "requested": "infojobs",
                "used": "mock",
                "fallback": True,
                "warning": str(error),
            }

    return read_json(MOCK_INPUT), {
        "requested": "mock",
        "used": "mock",
        "fallback": False,
        "warning": "InfoJobs está deshabilitado en config/searches.json",
    }


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
    suffix = f" (fallback: {status['warning']})" if status["fallback"] else ""
    print(
        f"Exportación {result['mode']} completada: "
        f"{result['summary']['valid']} válidas, "
        f"{result['summary']['discarded']} descartadas{suffix} -> "
        f"{OUTPUT.relative_to(ROOT)}"
    )
