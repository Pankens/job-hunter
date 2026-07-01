"""Genera el JSON estático del frontend a partir de datos mock."""

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

MOCK_INPUT = ROOT / "data" / "mock" / "source_jobs.json"
RULES_INPUT = ROOT / "config" / "filter_rules.json"
OUTPUT = ROOT / "web" / "src" / "data" / "jobs.json"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def export_jobs() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0)
    raw_jobs = read_json(MOCK_INPUT)
    rules = read_json(RULES_INPUT)

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
        "schemaVersion": 1,
        "generatedAt": generated_at.isoformat().replace("+00:00", "Z"),
        "mode": "mock",
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
    print(
        "Exportación mock completada: "
        f"{result['summary']['valid']} válidas, "
        f"{result['summary']['discarded']} descartadas -> {OUTPUT.relative_to(ROOT)}"
    )
