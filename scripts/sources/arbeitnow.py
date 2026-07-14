"""Arbeitnow public job-board API adapter."""

from __future__ import annotations

from typing import Any

from scripts.sources.api_common import compact_text, fetch_json, html_to_text, timestamp_to_iso
from scripts.sources.html_common import SourceRunResult, make_raw_job, stable_id


SOURCE = "arbeitnow"
API_URL = "https://www.arbeitnow.com/api/job-board-api"


def _to_raw(job: dict[str, Any]) -> dict[str, Any] | None:
    title = compact_text(job.get("title"))
    company = compact_text(job.get("company_name"))
    url = compact_text(job.get("url"))
    description = html_to_text(job.get("description"))
    if not title or not url:
        return None

    remote = bool(job.get("remote"))
    location = compact_text(job.get("location")) or ("Remote" if remote else "")
    city = "Remote" if remote else location.split(",", 1)[0].strip()
    source_id = compact_text(job.get("slug")) or stable_id(SOURCE, url, title, company)

    return make_raw_job(
        source=SOURCE,
        source_id=source_id,
        title=title,
        company=company,
        city=city,
        location=location,
        description=description,
        published_at=timestamp_to_iso(job.get("created_at")),
        url=url,
        query="technical",
        remote=remote,
        direct_url=True,
        warnings=["Arbeitnow public job-board API"],
    )


def collect(config: dict[str, Any], _queries: list[dict[str, str]]) -> SourceRunResult:
    result = SourceRunResult(source=SOURCE)
    source_config = config.get("source_registry", {}).get(SOURCE, {})
    timeout = int(source_config.get("timeout_seconds", config.get("timeout_seconds", 20)))
    max_pages = int(source_config.get("max_pages", 1))
    url = API_URL

    for _page in range(max_pages):
        try:
            status, payload = fetch_json(url, timeout)
            jobs = payload.get("data", []) if isinstance(payload, dict) else []
            before = len(result.jobs)
            for item in jobs:
                if isinstance(item, dict):
                    raw = _to_raw(item)
                    if raw:
                        result.jobs.append(raw)
            result.logs.append(
                {
                    "source": SOURCE,
                    "url": url,
                    "httpStatus": status,
                    "rawJobs": len(result.jobs) - before,
                    "error": "",
                }
            )
            next_url = payload.get("links", {}).get("next") if isinstance(payload, dict) else None
            if not next_url:
                break
            url = compact_text(next_url)
        except Exception as error:
            message = repr(error)
            result.errors.append(message)
            result.logs.append(
                {
                    "source": SOURCE,
                    "url": url,
                    "httpStatus": None,
                    "rawJobs": 0,
                    "error": message,
                }
            )
            break
    return result
