"""Orquestador de collectors HTML públicos."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.sources import generic_html, indeed_html, infojobs_html, tecnoempleo_html
from scripts.sources.html_common import stable_id


SOURCE_MODULES = {
    "infojobs_html": infojobs_html,
    "indeed_html": indeed_html,
    "tecnoempleo_html": tecnoempleo_html,
    "generic_html": generic_html,
}


def build_queries(config: dict[str, Any]) -> list[dict[str, str]]:
    queries: list[dict[str, str]] = []
    for city in config["locations"]:
        for query in config["general_queries"]:
            queries.append({"city": city, "query": query, "kind": "general"})
        for query in config["technical_queries"]:
            queries.append({"city": city, "query": query, "kind": "technical"})
    return queries


def deduplicate_raw_by_url(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for job in jobs:
        key = (job.get("url") or "").split("#", 1)[0].strip().lower()
        if not key:
            key = stable_id(
                job.get("source"),
                job.get("title"),
                job.get("company"),
                job.get("city"),
            )
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def collect_real_sources(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run_mode = os.environ.get("RUN_MODE", "local")
    if "JOB_HUNTER_DELAY_SECONDS" in os.environ:
        config = dict(config)
        config["delay_seconds"] = float(os.environ["JOB_HUNTER_DELAY_SECONDS"])
    if "JOB_HUNTER_MAX_PAGES_PER_QUERY" in os.environ:
        config = dict(config)
        config["max_pages_per_query"] = int(os.environ["JOB_HUNTER_MAX_PAGES_PER_QUERY"])
    if "JOB_HUNTER_USE_PLAYWRIGHT" in os.environ:
        config = dict(config)
        config["use_playwright"] = os.environ["JOB_HUNTER_USE_PLAYWRIGHT"].lower() in {
            "1",
            "true",
            "yes",
            "sí",
            "si",
        }
    mock_enabled = bool(config.get("use_mock", False))
    active_sources = [
        name for name, enabled in config.get("sources", {}).items() if enabled and name in SOURCE_MODULES
    ]
    queries = build_queries(config)
    raw_jobs: list[dict[str, Any]] = []
    source_reports: dict[str, Any] = {}

    print(f"RUN_MODE={run_mode}")
    print(f"MOCK_ENABLED={str(mock_enabled).lower()}")
    print(f"Fuentes activas: {', '.join(active_sources) or '(ninguna)'}")

    for source_name in active_sources:
        if source_name == "generic_html" and raw_jobs:
            print("== Fuente: generic_html ==")
            print("Saltada: ya se obtuvieron ofertas en fuentes prioritarias")
            source_reports[source_name] = {
                "rawJobs": 0,
                "errors": [],
                "usedPlaywright": False,
                "logs": [],
                "skipped": True,
                "skipReason": "Ya se obtuvieron ofertas en fuentes prioritarias",
            }
            continue
        module = SOURCE_MODULES[source_name]
        print(f"== Fuente: {source_name} ==")
        result = module.collect(config, queries)
        raw_jobs.extend(result.jobs)
        source_reports[source_name] = {
            "rawJobs": len(result.jobs),
            "errors": result.errors,
            "usedPlaywright": result.used_playwright,
            "logs": result.logs,
        }
        print(f"Ofertas raw por fuente {source_name}: {len(result.jobs)}")
        if result.used_playwright:
            print(f"Playwright usado por {source_name}: sí")
        for error in result.errors:
            print(f"ERROR {source_name}: {error}")
        for log in result.logs:
            print(
                "URL "
                f"{log['url']} | HTTP {log['httpStatus']} | "
                f"{log['htmlBytes']} bytes | "
                f"candidatos {log['candidatesDetected']} | "
                f"raw {log['rawJobs']} | "
                f"playwright {'sí' if log['usedPlaywright'] else 'no'} | "
                f"error {log['error'] or '-'}"
            )

    unique_raw = deduplicate_raw_by_url(raw_jobs)
    report = {
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "runMode": run_mode,
        "mockEnabled": mock_enabled,
        "activeSources": active_sources,
        "queriesCount": len(queries),
        "rawTotalBeforeSourceDedup": len(raw_jobs),
        "rawTotal": len(unique_raw),
        "sourceReports": source_reports,
    }
    print(f"Número total de ofertas raw: {len(raw_jobs)}")
    print(f"Número total de ofertas raw deduplicadas por URL: {len(unique_raw)}")
    return unique_raw, report


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
