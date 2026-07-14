"""Greenhouse Job Board API adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from scripts.sources.api_common import compact_text, fetch_json, html_to_text
from scripts.sources.html_common import SourceRunResult, make_raw_job, stable_id


SOURCE = "greenhouse"


def _location(job: dict[str, Any]) -> tuple[str, str, bool]:
    location = compact_text((job.get("location") or {}).get("name") if isinstance(job.get("location"), dict) else "")
    offices = job.get("offices") if isinstance(job.get("offices"), list) else []
    if not location and offices:
        location = compact_text(" / ".join(office.get("name", "") for office in offices if isinstance(office, dict)))
    normalized = location.lower()
    remote = "remote" in normalized or "teletrabajo" in normalized
    city = "Remote" if remote else location.split(",", 1)[0].strip()
    return city, location, remote


def _to_raw(job: dict[str, Any], company: dict[str, Any]) -> dict[str, Any] | None:
    title = compact_text(job.get("title"))
    url = compact_text(job.get("absolute_url"))
    description = html_to_text(job.get("content"))
    if not title or not url:
        return None
    city, location, remote = _location(job)
    company_name = compact_text(company.get("name") or company.get("board"))
    source_id = compact_text(job.get("id")) or stable_id(SOURCE, company.get("board"), url, title)
    return make_raw_job(
        source=SOURCE,
        source_id=source_id,
        title=title,
        company=company_name,
        city=city,
        location=location,
        description=description,
        url=url,
        query="technical",
        remote=remote,
        direct_url=True,
        warnings=[f"Greenhouse board: {company.get('board')}"],
    )


def collect(config: dict[str, Any], _queries: list[dict[str, str]]) -> SourceRunResult:
    result = SourceRunResult(source=SOURCE)
    source_config = config.get("source_registry", {}).get(SOURCE, {})
    timeout = int(source_config.get("timeout_seconds", config.get("timeout_seconds", 20)))
    companies = [company for company in source_config.get("companies", []) if company.get("enabled", True)]

    for company in companies:
        board = compact_text(company.get("board"))
        if not board:
            continue
        url = f"https://boards-api.greenhouse.io/v1/boards/{quote(board)}/jobs?content=true"
        try:
            status, payload = fetch_json(url, timeout)
            jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
            before = len(result.jobs)
            for item in jobs:
                if isinstance(item, dict):
                    raw = _to_raw(item, company)
                    if raw:
                        result.jobs.append(raw)
            result.logs.append(
                {
                    "source": SOURCE,
                    "url": url,
                    "company": company.get("name") or board,
                    "httpStatus": status,
                    "rawJobs": len(result.jobs) - before,
                    "error": "",
                }
            )
        except Exception as error:
            message = f"{company.get('name') or board}: {error!r}"
            result.errors.append(message)
            result.logs.append(
                {
                    "source": SOURCE,
                    "url": url,
                    "company": company.get("name") or board,
                    "httpStatus": None,
                    "rawJobs": 0,
                    "error": message,
                }
            )
    return result
