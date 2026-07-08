"""Fuentes de InfoJobs.

V1 usa feeds/RSS públicos y no requiere credenciales. La integración con la API
oficial se conserva aislada para poder retomarla más adelante si hay acceso al
portal developer.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen

from scripts.normalize import comparable_text


CLIENT_ID_ENV = "INFOJOBS_CLIENT_ID"
CLIENT_SECRET_ENV = "INFOJOBS_CLIENT_SECRET"
DEFAULT_FEED_TEMPLATE = "https://www.infojobs.net/trabajos.feed?keyword={query}&city={city}"
RSS_LIMITED_DESCRIPTION_WARNING = "Descripción limitada por RSS"


class InfoJobsSourceError(RuntimeError):
    """Error recuperable que hará que el pipeline use datos mock."""

    def __init__(self, message: str, stats: "FeedFetchStats | None" = None) -> None:
        super().__init__(message)
        self.stats = stats


class InfoJobsCredentialsMissing(InfoJobsSourceError):
    """Las credenciales de aplicación no están configuradas."""


@dataclass(frozen=True)
class InfoJobsCredentials:
    client_id: str
    client_secret: str

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "InfoJobsCredentials":
        values = os.environ if environment is None else environment
        client_id = values.get(CLIENT_ID_ENV, "").strip()
        client_secret = values.get(CLIENT_SECRET_ENV, "").strip()
        if not client_id or not client_secret:
            raise InfoJobsCredentialsMissing(
                f"Faltan {CLIENT_ID_ENV} y/o {CLIENT_SECRET_ENV}"
            )
        return cls(client_id=client_id, client_secret=client_secret)


@dataclass(frozen=True)
class FeedFetchStats:
    source: str
    feeds_consulted: int
    offers_obtained: int
    errors: list[str]


def _dictionary_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or "").strip()
    return str(value or "").strip()


def _salary_number(value: Any) -> float | None:
    text = _dictionary_value(value)
    match = re.search(r"\d[\d.,]*", text)
    if not match:
        return None
    digits = re.sub(r"[^\d]", "", match.group())
    return float(digits) if digits else None


def _monthly_salary(offer: dict[str, Any]) -> float | None:
    minimum = _salary_number(offer.get("salaryMin"))
    period = comparable_text(_dictionary_value(offer.get("salaryPeriod")))
    if minimum is None:
        return None
    if "ano" in period or "year" in period:
        return round(minimum / 12, 2)
    if "mes" in period or "month" in period:
        return minimum
    return None


def _strip_html(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _first_text(element: ET.Element, names: Iterable[str]) -> str:
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def _namespaced_text(element: ET.Element, local_names: Iterable[str]) -> str:
    wanted = set(local_names)
    for child in element:
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name in wanted and child.text:
            return child.text.strip()
    return ""


def _entry_link(element: ET.Element) -> str:
    direct = _first_text(element, ["link"])
    if direct:
        return direct
    for child in element:
        if child.tag.rsplit("}", 1)[-1] == "link":
            href = child.attrib.get("href", "").strip()
            if href:
                return href
    return ""


def _entry_id(entry: ET.Element, link: str, title: str) -> str:
    guid = _first_text(entry, ["guid", "id"]) or _namespaced_text(entry, ["guid", "id"])
    if guid:
        return guid
    match = re.search(r"/of-([a-z0-9]+)", link, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return f"{title}|{link}"


def _infer_city(*values: Any, configured_city: str = "") -> str:
    haystack = comparable_text(" ".join(str(value or "") for value in values))
    for city in ("Valencia", "Paterna", "Burjassot"):
        if comparable_text(city) in haystack:
            return city
    return configured_city


def _infer_company(title: str) -> str:
    separators = (" - ", " – ", " | ", " en ")
    for separator in separators:
        if separator in title:
            left, right = title.rsplit(separator, 1)
            if left.strip() and right.strip():
                return right.strip()[:120]
    return ""


def _build_feed_url(template: str, query: str, city: str) -> str:
    return template.format(
        query=quote(query),
        query_plus=quote(query.replace(" ", "+"), safe="+"),
        city=quote(city),
        city_slug=quote(comparable_text(city).replace(" ", "-")),
    )


def build_infojobs_feed_urls(settings: dict[str, Any]) -> list[dict[str, str]]:
    """Construye URLs RSS a partir de ciudades, búsquedas y plantillas."""
    templates = settings.get("feed_url_templates") or [DEFAULT_FEED_TEMPLATE]
    urls: list[dict[str, str]] = []
    seen: set[str] = set()
    for city in settings["cities"]:
        for search in settings["searches"]:
            query = str(search.get("query") or "").strip()
            for template in templates:
                url = _build_feed_url(template, query=query, city=city)
                if url not in seen:
                    seen.add(url)
                    urls.append(
                        {
                            "url": url,
                            "city": city,
                            "search": str(search.get("name") or query or "general"),
                            "query": query,
                        }
                    )
    return urls


def parse_infojobs_feed(
    xml_bytes: bytes,
    *,
    feed_url: str,
    configured_city: str,
) -> list[dict[str, Any]]:
    """Convierte RSS/Atom de InfoJobs al contrato raw común del pipeline."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise InfoJobsSourceError(f"Feed XML no válido: {feed_url}") from error

    entries = root.findall(".//item")
    if not entries:
        entries = [
            element
            for element in root.findall(".//{http://www.w3.org/2005/Atom}entry")
        ]

    jobs: list[dict[str, Any]] = []
    for entry in entries:
        title = _strip_html(
            _first_text(entry, ["title"]) or _namespaced_text(entry, ["title"])
        )
        link = _entry_link(entry)
        summary = _strip_html(
            _first_text(entry, ["description", "summary", "content"])
            or _namespaced_text(entry, ["description", "summary", "content"])
        )
        published_at = (
            _first_text(entry, ["pubDate", "published", "updated", "date"])
            or _namespaced_text(entry, ["pubDate", "published", "updated", "date"])
            or None
        )
        location = _strip_html(
            _namespaced_text(entry, ["location", "jobLocation", "city"])
        )
        company = _strip_html(_namespaced_text(entry, ["company", "author"]))
        city = _infer_city(title, summary, location, link, configured_city=configured_city)

        if not title and not link:
            continue

        jobs.append(
            {
                "source": "infojobs",
                "source_id": _entry_id(entry, link, title),
                "title": title,
                "company": company or _infer_company(title),
                "city": city,
                "location": location or city,
                "description": summary,
                "requirements": summary,
                "required_languages": [],
                "salary_text": "",
                "salary_base_eur_month": None,
                "has_commission": "comision" in comparable_text(f"{title} {summary}"),
                "published_at": published_at,
                "url": link or feed_url,
                "source_warnings": [RSS_LIMITED_DESCRIPTION_WARNING],
            }
        )
    return jobs


def fetch_infojobs_rss_jobs(
    settings: dict[str, Any],
    opener: Callable[..., Any] = urlopen,
) -> tuple[list[dict[str, Any]], FeedFetchStats]:
    """Consulta feeds públicos de InfoJobs y devuelve ofertas raw sin credenciales."""
    urls = build_infojobs_feed_urls(settings)
    timeout_seconds = int(settings.get("timeout_seconds", 20))
    raw_by_id: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    consulted = 0

    for feed in urls:
        request = Request(
            feed["url"],
            headers={
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
                "User-Agent": "job-hunter/1.0 (+https://github.com/)",
            },
            method="GET",
        )
        try:
            consulted += 1
            with opener(request, timeout=timeout_seconds) as response:
                xml_bytes = response.read()
            for job in parse_infojobs_feed(
                xml_bytes, feed_url=feed["url"], configured_city=feed["city"]
            ):
                source_id = str(job.get("source_id") or "").strip()
                if source_id:
                    raw_by_id[source_id] = job
        except HTTPError as error:
            errors.append(f"{feed['search']} · {feed['city']}: HTTP {error.code}")
        except (URLError, TimeoutError, OSError) as error:
            reason = error.reason if isinstance(error, URLError) else error
            errors.append(f"{feed['search']} · {feed['city']}: {reason}")
        except InfoJobsSourceError as error:
            errors.append(f"{feed['search']} · {feed['city']}: {error}")

    jobs = list(raw_by_id.values())
    if not jobs:
        stats = FeedFetchStats(
            source="InfoJobs RSS",
            feeds_consulted=consulted,
            offers_obtained=0,
            errors=errors,
        )
        detail = "; ".join(errors[:5]) if errors else "los feeds no devolvieron ofertas"
        raise InfoJobsSourceError(
            f"InfoJobs RSS no devolvió ofertas ({detail})",
            stats=stats,
        )

    return jobs, FeedFetchStats(
        source="InfoJobs RSS",
        feeds_consulted=consulted,
        offers_obtained=len(jobs),
        errors=errors,
    )


def fetch_infojobs_jobs(
    settings: dict[str, Any],
    opener: Callable[..., Any] = urlopen,
) -> tuple[list[dict[str, Any]], FeedFetchStats]:
    """Entrada principal de V1: InfoJobs RSS/feed sin credenciales."""
    return fetch_infojobs_rss_jobs(settings, opener=opener)


def map_offer_to_raw(offer: dict[str, Any]) -> dict[str, Any]:
    """Adapta una oferta de la API oficial al contrato raw común del pipeline.

    Se mantiene para una opción futura, pero V1 no la usa.
    """
    requirements = str(offer.get("requirementMin") or "").strip()
    salary_text = str(offer.get("salaryDescription") or "").strip()
    published_at = offer.get("published") or offer.get("updated")
    city = str(offer.get("city") or "").strip()
    province = _dictionary_value(offer.get("province"))
    warnings: list[str] = [
        "InfoJobs no proporciona la descripción completa en el listado; se usan los requisitos mínimos"
    ]
    if not requirements:
        warnings.append("InfoJobs no proporcionó requisitos ni descripción para esta oferta")
    if not salary_text:
        warnings.append("InfoJobs no proporcionó información salarial")
    if not published_at:
        warnings.append(
            "InfoJobs no proporcionó fecha de publicación; se usará la fecha de exportación"
        )

    return {
        "source": "infojobs",
        "source_id": str(offer.get("id") or "").strip(),
        "title": str(offer.get("title") or "").strip(),
        "company": str((offer.get("author") or {}).get("name") or "").strip(),
        "city": city,
        "location": " · ".join(part for part in (city, province) if part),
        "description": requirements,
        "requirements": requirements,
        "required_languages": [],
        "salary_text": salary_text,
        "salary_base_eur_month": _monthly_salary(offer),
        "has_commission": "comision" in comparable_text(
            f"{salary_text} {requirements}"
        ),
        "published_at": published_at,
        "url": str(offer.get("link") or "").strip(),
        "source_warnings": warnings,
    }


class InfoJobsClient:
    """Cliente de la API oficial, reservado para una integración futura."""

    def __init__(
        self,
        credentials: InfoJobsCredentials,
        api_url: str,
        timeout_seconds: int = 20,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.credentials = credentials
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.opener = opener

    def search(self, params: dict[str, Any]) -> dict[str, Any]:
        token = base64.b64encode(
            f"{self.credentials.client_id}:{self.credentials.client_secret}".encode("utf-8")
        ).decode("ascii")
        request = Request(
            f"{self.api_url}?{urlencode(params)}",
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
                "User-Agent": "job-hunter/1.0",
            },
            method="GET",
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except HTTPError as error:
            raise InfoJobsSourceError(
                f"InfoJobs API respondió HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            reason = error.reason if isinstance(error, URLError) else error
            raise InfoJobsSourceError(f"No se pudo conectar con InfoJobs API: {reason}") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise InfoJobsSourceError("InfoJobs API devolvió JSON no válido") from error

        if not isinstance(payload, dict) or not isinstance(payload.get("offers"), list):
            raise InfoJobsSourceError("La respuesta de InfoJobs API no contiene ofertas")
        return payload
