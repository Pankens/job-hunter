"""Collectors HTML públicos de respaldo: Trabajos.com, Jobatus y Jooble."""

from __future__ import annotations

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


SOURCE = "generic"


def build_urls(query: str, city: str, max_pages: int) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    for _page in range(1, max_pages + 1):
        urls.extend(
            [
                (
                    "trabajos_com",
                    f"https://www.trabajos.com/ofertas-empleo/?CADENA={encoded(query)}&IDPAIS=100&IDPROVINCIA=46",
                ),
                (
                    "jobatus",
                    f"https://www.jobatus.es/trabajo-{encoded(query)}-en-{encoded(city)}",
                ),
                (
                    "jooble",
                    f"https://es.jooble.org/SearchResult?rgns={encoded(city)}&ukw={encoded(query)}",
                ),
            ]
        )
        break
    return urls


def collect(settings: dict, queries: list[dict[str, str]]) -> SourceRunResult:
    result = SourceRunResult(source="generic_html")
    max_pages = int(settings.get("max_pages_per_query", 1))
    delay = float(settings.get("delay_seconds", 0))
    use_playwright = bool(settings.get("use_playwright", True))

    for item in queries:
        query = item["query"]
        city = item["city"]
        for site_name, url in build_urls(query, city, max_pages):
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
                        source=site_name,
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
                            r"/oferta",
                            r"/trabajo",
                            r"/job/",
                            r"jooble\.org/desc/",
                            r"jobatus\.es/.+",
                        ],
                        exclude_patterns=[r"/empresa", r"/login", r"/candidato", r"/blog"],
                        limit=20,
                    )
                    candidates_count = len(candidates)
                    for candidate in candidates:
                        result.jobs.append(
                            make_raw_job(
                                source=site_name,
                                title=_clean_title(candidate["title"], query),
                                city=city,
                                location=city,
                                url=candidate["url"],
                                query=query,
                                warnings=[f"Oferta detectada por enlace público de {site_name}"],
                            )
                        )
            except Exception as exc:
                error = repr(exc)
                result.errors.append(f"{url}: {error}")
            finally:
                result.logs.append(
                    build_log(
                        source=f"generic_html:{site_name}",
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


def _clean_title(title: str, query: str) -> str:
    cleaned = compact_text(title)
    if len(cleaned) > 160:
        cleaned = cleaned[:157] + "..."
    return cleaned or query


def _looks_blocked_or_empty(html: str) -> bool:
    lowered = html.lower()
    return len(html) < 2500 or "captcha" in lowered or "access denied" in lowered
