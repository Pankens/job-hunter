"""Collector HTML público de Tecnoempleo para ofertas técnicas."""

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


SOURCE = "tecnoempleo"


def build_urls(query: str, city: str, max_pages: int) -> list[str]:
    urls = []
    for page in range(1, max_pages + 1):
        urls.append(
            "https://www.tecnoempleo.com/ofertas-trabajo/"
            f"?te={encoded(query)}&pr={encoded(city)}&pagina={page}"
        )
    return urls


def collect(settings: dict, queries: list[dict[str, str]]) -> SourceRunResult:
    result = SourceRunResult(source="tecnoempleo_html")
    max_pages = int(settings.get("max_pages_per_query", 1))
    delay = float(settings.get("delay_seconds", 0))
    use_playwright = bool(settings.get("use_playwright", True))
    technical_queries = [item for item in queries if item.get("kind") == "technical"]

    for item in technical_queries:
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
                if _looks_js_or_blocked(html) and use_playwright:
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
                    cards = soup.select("article, .oferta, .job, .card, [class*=oferta], [class*=job]")
                    candidates_count = len(cards)
                    for card in cards[:25]:
                        anchor = card.select_one("a[href]")
                        if not anchor:
                            continue
                        title = compact_text(anchor.get_text(" ", strip=True))
                        href = anchor.get("href") or ""
                        if not title or "oferta" not in href.lower() and "trabajo" not in href.lower():
                            continue
                        text = compact_text(card.get_text(" ", strip=True))
                        result.jobs.append(
                            make_raw_job(
                                source=SOURCE,
                                title=title,
                                city=city,
                                location=city,
                                description=text[:500],
                                url=_absolute(href),
                                query=query,
                                warnings=["Oferta extraída del listado público de Tecnoempleo"],
                            )
                        )

                if len(result.jobs) == jobs_before:
                    candidates = extract_link_candidates(
                        soup,
                        base_url=url,
                        include_patterns=[r"tecnoempleo\.com/.+oferta", r"/oferta", r"/trabajo"],
                        exclude_patterns=[r"/empresa", r"/login", r"/candidatos"],
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
                                warnings=["Oferta detectada por enlace público de Tecnoempleo"],
                            )
                        )
            except Exception as exc:
                error = repr(exc)
                result.errors.append(f"{url}: {error}")
            finally:
                result.logs.append(
                    build_log(
                        source="tecnoempleo_html",
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


def _absolute(href: str) -> str:
    if href.startswith("http"):
        return href
    return f"https://www.tecnoempleo.com/{href.lstrip('/')}"


def _looks_js_or_blocked(html: str) -> bool:
    lowered = html.lower()
    return len(html) < 3000 or "access denied" in lowered or "captcha" in lowered
