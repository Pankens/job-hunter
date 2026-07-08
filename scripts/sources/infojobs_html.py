"""Collector HTML público de InfoJobs, sin login ni API."""

from __future__ import annotations

from bs4 import BeautifulSoup

from scripts.sources.html_common import (
    SourceRunResult,
    build_log,
    encoded,
    extract_link_candidates,
    fetch_with_playwright,
    fetch_with_requests,
    iter_json_ld_jobs,
    jsonld_to_raw,
    make_raw_job,
    sleep_between_requests,
)


SOURCE = "infojobs"


def build_urls(query: str, city: str, max_pages: int) -> list[str]:
    slug_city = encoded(city).replace("+", "-").lower()
    slug_query = encoded(query).replace("+", "-").lower()
    urls = [f"https://www.infojobs.net/ofertas-trabajo/{slug_city}/{slug_query}"]
    if max_pages > 1:
        urls.extend(f"{urls[0]}/{page}" for page in range(2, max_pages + 1))
    return urls


def collect(settings: dict, queries: list[dict[str, str]]) -> SourceRunResult:
    result = SourceRunResult(source="infojobs_html")
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
                if _looks_blocked_or_empty(html) and use_playwright:
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
                    candidates = extract_link_candidates(
                        soup,
                        base_url=url,
                        include_patterns=[
                            r"/of-[a-z0-9]+",
                            r"/ofertas-trabajo/.+",
                            r"infojobs\.net/.+/of-",
                        ],
                        exclude_patterns=[r"/candidate/", r"/empresa/", r"/login"],
                    )
                    candidates_count = len(candidates)
                    for candidate in candidates:
                        result.jobs.append(
                            make_raw_job(
                                source=SOURCE,
                                title=candidate["title"],
                                city=city,
                                location=city,
                                url=candidate["url"],
                                query=query,
                                warnings=["Oferta detectada por enlace público de InfoJobs"],
                            )
                        )
                else:
                    candidates_count = len(result.jobs) - jobs_before
            except Exception as exc:  # network/selectors must not kill whole run
                error = repr(exc)
                result.errors.append(f"{url}: {error}")
            finally:
                result.logs.append(
                    build_log(
                        source="infojobs_html",
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


def _looks_blocked_or_empty(html: str) -> bool:
    lowered = html.lower()
    return (
        len(html) < 5000
        or "request could not be satisfied" in lowered
        or "access denied" in lowered
        or "__next" in lowered and "jobposting" not in lowered and "/of-" not in lowered
    )
