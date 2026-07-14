"""Lever Postings API adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from scripts.sources.api_common import compact_text, fetch_json, html_to_text, timestamp_ms_to_iso
from scripts.sources.html_common import SourceRunResult, make_raw_job, stable_id


SOURCE = "lever"


def _categories(job: dict[str, Any]) -> dict[str, Any]:
    return job.get("categories") if isinstance(job.get("categories"), dict) else {}


def _to_raw(job: dict[str, Any], company: dict[str, Any]) -> dict[str, Any] | None:
    title = compact_text(job.get("text"))
    url = compact_text(job.get("hostedUrl") or job.get("applyUrl"))
    description = html_to_text(job.get("descriptionPlain") or job.get("description"))
    if not title or not url:
        return None

    categories = _categories(job)
    location = compact_text(categories.get("location"))
    normalized = location.lower()
    remote = "remote" in normalized or "teletrabajo" in normalized
    city = "Remote" if remote else location.split(",", 1)[0].strip()
    company_name = compact_text(company.get("name") or company.get("company"))
    source_id = compact_text(job.get("id")) or stable_id(SOURCE, company.get("company"), url, title)

    return make_raw_job(
        source=SOURCE,
        source_id=source_id,
        title=title,
        company=company_name,
        city=city,
        location=location,
        description=description,
        published_at=timestamp_ms_to_iso(job.get("createdAt")),
        url=url,
        query=compact_text(categories.get("team") or "technical"),
        remote=remote,
        direct_url=True,
        warnings=[f"Lever company: {company.get('company')}"],
    )


def collect(config: dict[str, Any], _queries: list[dict[str, str]]) -> SourceRunResult:
    result = SourceRunResult(source=SOURCE)
    source_config = config.get("source_registry", {}).get(SOURCE, {})
    timeout = int(source_config.get("timeout_seconds", config.get("timeout_seconds", 20)))
    companies = [company for company in source_config.get("companies", []) if company.get("enabled", True)]

    for company in companies:
        slug = compact_text(company.get("company"))
        if not slug:
            continue
        url = f"https://api.lever.co/v0/postings/{quote(slug)}?mode=json"
        try:
            status, payload = fetch_json(url, timeout)
            jobs = payload if isinstance(payload, list) else []
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
                    "company": company.get("name") or slug,
                    "httpStatus": status,
                    "rawJobs": len(result.jobs) - before,
                    "error": "",
                }
            )
        except Exception as error:
            message = f"{company.get('name') or slug}: {error!r}"
            result.errors.append(message)
            result.logs.append(
                {
                    "source": SOURCE,
                    "url": url,
                    "company": company.get("name") or slug,
                    "httpStatus": None,
                    "rawJobs": 0,
                    "error": message,
                }
            )
    return result
