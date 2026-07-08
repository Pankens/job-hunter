"""Collector HTML público de Indeed, sin login ni API."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scripts.sources.html_common import (
    SourceRunResult,
    build_log,
    compact_text,
    encoded,
    extract_link_candidates,
    fetch_with_playwright,
    fetch_with_requests,
    iter_json_ld_jobs,
    jsonld_to_raw,
    make_raw_job,
    sleep_between_requests,
)


SOURCE = "indeed"


def build_urls(query: str, city: str, max_pages: int) -> list[str]:
    urls = []
    for page in range(max_pages):
        start = page * 10
        urls.append(f"https://es.indeed.com/jobs?q={encoded(query)}&l={encoded(city)}&start={start}")
    return urls


def collect(settings: dict, queries: list[dict[str, str]]) -> SourceRunResult:
    result = SourceRunResult(source="indeed_html")
    max_pages = int(settings.get("max_pages_per_query", 1))
    delay = float(settings.get("delay_seconds", 0))
    use_playwright = bool(settings.get("use_playwright", True))

    for item in queries:
        query = item["query"]
        city = item["city"]
        for url in build_urls(query, city, max_pages):
            status = None
            html = ""
            used_playwright = False
            error = ""
            jobs_before = len(result.jobs)
            candidates_count = 0
            try:
                status, html = fetch_with_requests(url)
                if _looks_blocked_or_js(html) and use_playwright:
                    status, html = fetch_with_playwright(url)
                    used_playwright = True
                    result.used_playwright = True
                soup = BeautifulSoup(html, "html.parser")

                for node in iter_json_ld_jobs(soup):
                    raw = jsonld_to_raw(
                        node,
                        source=SOURCE,
                        base_url=url,
                        city=city,
                        query=query,
                    )
                    if raw:
                        result.jobs.append(raw)

                if len(result.jobs) == jobs_before:
                    cards = soup.select("[data-jk], .job_seen_beacon, .result, [class*=job_seen_beacon]")
                    candidates_count = len(cards)
                    for card in cards[:25]:
                        anchor = card.select_one("a[href*='/viewjob'], a[href*='jk='], h2 a[href]")
                        if not anchor:
                            continue
                        title = compact_text(anchor.get_text(" ", strip=True))
                        href = anchor.get("href") or ""
                        if not title:
                            continue
                        company = compact_text(
                            _first_text(card, [
                                "[data-testid='company-name']",
                                ".companyName",
                                ".css-1h7lukg",
                            ])
                        )
                        location = compact_text(
                            _first_text(card, [
                                "[data-testid='text-location']",
                                ".companyLocation",
                            ])
                        )
                        salary = compact_text(_first_text(card, [".salary-snippet", "[data-testid='attribute_snippet_testid']"]))
                        summary = compact_text(_first_text(card, [".job-snippet", ".summary"]))
                        result.jobs.append(
                            make_raw_job(
                                source=SOURCE,
                                title=title,
                                company=company,
                                city=city,
                                location=location or city,
                                salary_text=salary,
                                description=summary,
                                url=_indeed_url(url, href),
                                query=query,
                                warnings=["Oferta extraída del listado público de Indeed"],
                            )
                        )

                if len(result.jobs) == jobs_before:
                    candidates = extract_link_candidates(
                        soup,
                        base_url=url,
                        include_patterns=[r"/viewjob", r"jk="],
                        exclude_patterns=[r"/companies", r"/career"],
                    )
                    candidates_count = max(candidates_count, len(candidates))
                    for candidate in candidates:
                        result.jobs.append(
                            make_raw_job(
                                source=SOURCE,
                                title=candidate["title"],
                                city=city,
                                location=city,
                                url=candidate["url"],
                                query=query,
                                warnings=["Oferta detectada por enlace público de Indeed"],
                            )
                        )
            except Exception as exc:
                error = repr(exc)
                result.errors.append(f"{url}: {error}")
            finally:
                result.logs.append(
                    build_log(
                        source="indeed_html",
                        url=url,
                        query=query,
                        city=city,
                        status=status,
                        html=html,
                        candidates=candidates_count,
                        raw_jobs=len(result.jobs) - jobs_before,
                        error=error,
                        used_playwright=used_playwright,
                    )
                )
                sleep_between_requests(delay)
    return result


def _first_text(card, selectors: list[str]) -> str:
    for selector in selectors:
        found = card.select_one(selector)
        if found:
            return found.get_text(" ", strip=True)
    return ""


def _indeed_url(base_url: str, href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"https://es.indeed.com{href}"
    match = re.search(r"jk=([a-zA-Z0-9]+)", href)
    if match:
        return f"https://es.indeed.com/viewjob?jk={match.group(1)}"
    return base_url


def _looks_blocked_or_js(html: str) -> bool:
    lowered = html.lower()
    return (
        "captcha" in lowered
        or "unusual traffic" in lowered
        or "enable javascript" in lowered
        or ("mosaic-provider-jobcards" not in lowered and "/viewjob" not in lowered)
    )
