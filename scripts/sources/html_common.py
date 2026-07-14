"""Utilidades comunes para colectores HTML públicos de empleo."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from scripts.normalize import comparable_text


TECHNICAL_QUERY_HINTS = {
    "programador",
    "desarrollador",
    "frontend",
    "backend",
    "full stack",
    "java",
    "javascript",
    "typescript",
    "vue",
    "angular",
    "html",
    "css",
    "scss",
    "figma",
    "mongodb",
    "mysql",
    "diseno web",
    "informatico",
    "soporte tecnico",
}


@dataclass
class SourceRunResult:
    source: str
    jobs: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    used_playwright: bool = False


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def preview_html(html: str, limit: int = 300) -> str:
    return compact_text(html)[:limit]


def stable_id(*parts: Any) -> str:
    seed = "|".join(compact_text(part).lower() for part in parts if compact_text(part))
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def infer_type(query: str, title: str = "", description: str = "") -> str:
    haystack = comparable_text(f"{query} {title} {description}")
    return "technical" if any(term in haystack for term in TECHNICAL_QUERY_HINTS) else "general"


def source_warning(*values: str) -> list[str]:
    return [value for value in values if value]


def make_raw_job(
    *,
    source: str,
    title: str,
    url: str,
    city: str,
    query: str,
    company: str = "",
    location: str = "",
    published_at: str | None = None,
    salary_text: str = "",
    description: str = "",
    source_id: str = "",
    remote: bool = False,
    direct_url: bool = False,
    warnings: Iterable[str] = (),
) -> dict[str, Any]:
    title = compact_text(title)
    url = compact_text(url)
    company = compact_text(company)
    location = compact_text(location) or city
    description = compact_text(description)
    salary_text = compact_text(salary_text)
    if not source_id:
        source_id = stable_id(source, url, title, company, city)

    missing_warnings = []
    if not company:
        missing_warnings.append("Empresa no disponible en el listado público")
    if not description:
        missing_warnings.append("Descripción limitada o no disponible en el listado público")
    if not published_at:
        missing_warnings.append("Fecha de publicación no disponible en el listado público")

    return {
        "source": source,
        "source_id": source_id,
        "title": title,
        "company": company,
        "city": city,
        "location": location,
        "remote": remote,
        "description": description,
        "requirements": description,
        "required_languages": [],
        "salary_text": salary_text,
        "salary_base_eur_month": None,
        "has_commission": "comision" in comparable_text(f"{title} {description} {salary_text}"),
        "published_at": published_at,
        "url": url,
        "direct_url": direct_url,
        "source_warnings": list(dict.fromkeys([*warnings, *missing_warnings])),
        "raw_type_hint": infer_type(query, title, description),
    }


def build_log(
    *,
    source: str,
    url: str,
    query: str,
    city: str,
    status: int | None,
    html: str,
    candidates: int,
    raw_jobs: int,
    error: str = "",
    used_playwright: bool = False,
) -> dict[str, Any]:
    return {
        "source": source,
        "url": url,
        "query": query,
        "city": city,
        "httpStatus": status,
        "htmlBytes": len(html.encode("utf-8", errors="replace")),
        "preview": preview_html(html),
        "candidatesDetected": candidates,
        "rawJobs": raw_jobs,
        "error": error,
        "usedPlaywright": used_playwright,
    }


def fetch_with_requests(url: str, timeout_seconds: int = 20) -> tuple[int, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=timeout_seconds)
    return response.status_code, response.text


def fetch_with_playwright(url: str, timeout_seconds: int = 25) -> tuple[int | None, str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as error:  # pragma: no cover - depends on optional runtime install
        raise RuntimeError(f"Playwright no disponible: {error}") from error

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="es-ES")
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
        page.wait_for_timeout(1500)
        html = page.content()
        status = response.status if response else None
        browser.close()
        return status, html


def sleep_between_requests(delay_seconds: float) -> None:
    if delay_seconds > 0:
        time.sleep(delay_seconds)


def iter_json_ld_jobs(soup: BeautifulSoup) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        expanded: list[dict[str, Any]] = []
        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("@graph"), list):
                expanded.extend(item for item in node["@graph"] if isinstance(item, dict))
            elif isinstance(node, dict):
                expanded.append(node)
        for node in expanded:
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if any(str(item).lower() == "jobposting" for item in types):
                jobs.append(node)
    return jobs


def jsonld_to_raw(
    node: dict[str, Any],
    *,
    source: str,
    base_url: str,
    city: str,
    query: str,
) -> dict[str, Any] | None:
    title = compact_text(node.get("title"))
    url = compact_text(node.get("url")) or base_url
    url = urljoin(base_url, url)
    if not title:
        return None
    hiring = node.get("hiringOrganization") or {}
    company = hiring.get("name") if isinstance(hiring, dict) else ""
    location = _job_location_text(node.get("jobLocation")) or city
    salary_text = _salary_text(node.get("baseSalary"))
    description = compact_text(node.get("description"))
    published_at = compact_text(node.get("datePosted")) or None
    return make_raw_job(
        source=source,
        title=title,
        company=company or "",
        city=city,
        location=location,
        description=description,
        salary_text=salary_text,
        published_at=published_at,
        url=url,
        query=query,
        source_id=stable_id(source, url, title, company or "", city),
        warnings=["Oferta extraída desde JSON-LD público"],
    )


def _job_location_text(value: Any) -> str:
    if isinstance(value, list):
        return " · ".join(filter(None, (_job_location_text(item) for item in value)))
    if not isinstance(value, dict):
        return ""
    address = value.get("address")
    if isinstance(address, dict):
        return compact_text(
            " · ".join(
                str(address.get(part) or "")
                for part in ("addressLocality", "addressRegion", "addressCountry")
                if address.get(part)
            )
        )
    return compact_text(value.get("name"))


def _salary_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    amount = value.get("value")
    currency = value.get("currency") or "EUR"
    if isinstance(amount, dict):
        min_value = amount.get("minValue")
        max_value = amount.get("maxValue")
        unit = amount.get("unitText") or ""
        if min_value and max_value:
            return compact_text(f"{min_value} - {max_value} {currency} {unit}")
        if amount.get("value"):
            return compact_text(f"{amount['value']} {currency} {unit}")
    return ""


def extract_link_candidates(
    soup: BeautifulSoup,
    *,
    base_url: str,
    include_patterns: Iterable[str],
    exclude_patterns: Iterable[str] = (),
    limit: int = 25,
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    include = [re.compile(pattern, re.I) for pattern in include_patterns]
    exclude = [re.compile(pattern, re.I) for pattern in exclude_patterns]
    for anchor in soup.select("a[href]"):
        href = anchor.get("href") or ""
        text = compact_text(anchor.get_text(" ", strip=True))
        absolute = urljoin(base_url, href)
        haystack = f"{absolute} {text}"
        if not text or len(text) < 4:
            continue
        if not any(pattern.search(haystack) for pattern in include):
            continue
        if any(pattern.search(haystack) for pattern in exclude):
            continue
        key = absolute.split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"title": text, "url": key})
        if len(candidates) >= limit:
            break
    return candidates


def encoded(value: str) -> str:
    return quote_plus(value)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
