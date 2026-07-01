"""Cliente de la API oficial de búsqueda pública de InfoJobs."""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.normalize import comparable_text


CLIENT_ID_ENV = "INFOJOBS_CLIENT_ID"
CLIENT_SECRET_ENV = "INFOJOBS_CLIENT_SECRET"


class InfoJobsSourceError(RuntimeError):
    """Error recuperable que hará que el pipeline use datos mock."""


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


def map_offer_to_raw(offer: dict[str, Any]) -> dict[str, Any]:
    """Adapta una oferta de InfoJobs al contrato raw común del pipeline."""
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
    """Cliente pequeño, sin dependencias externas y fácil de sustituir en tests."""

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
                f"InfoJobs respondió HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise InfoJobsSourceError(
                f"No se pudo conectar con InfoJobs: {error.reason if isinstance(error, URLError) else error}"
            ) from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise InfoJobsSourceError("InfoJobs devolvió una respuesta JSON no válida") from error

        if not isinstance(payload, dict) or not isinstance(payload.get("offers"), list):
            raise InfoJobsSourceError("La respuesta de InfoJobs no contiene una lista de ofertas")
        return payload


def fetch_infojobs_jobs(
    settings: dict[str, Any],
    environment: Mapping[str, str] | None = None,
    opener: Callable[..., Any] = urlopen,
) -> list[dict[str, Any]]:
    """Ejecuta las búsquedas configuradas y devuelve ofertas en formato raw."""
    credentials = InfoJobsCredentials.from_environment(environment)
    client = InfoJobsClient(
        credentials=credentials,
        api_url=settings["api_url"],
        timeout_seconds=int(settings.get("timeout_seconds", 20)),
        opener=opener,
    )
    requested_cities = {
        comparable_text(city): city for city in settings["cities"]
    }
    max_pages = max(1, int(settings.get("max_pages_per_search", 1)))
    page_size = min(50, max(1, int(settings.get("max_results_per_page", 50))))
    raw_by_id: dict[str, dict[str, Any]] = {}

    for city in settings["cities"]:
        for search in settings["searches"]:
            page = 1
            while page <= max_pages:
                params: dict[str, Any] = {
                    "city": comparable_text(city),
                    "sinceDate": settings.get("since_date", "_7_DAYS"),
                    "order": "updated-desc",
                    "page": page,
                    "maxResults": page_size,
                }
                if search.get("query"):
                    params["q"] = search["query"]

                payload = client.search(params)
                for offer in payload["offers"]:
                    offer_city = comparable_text(offer.get("city"))
                    offer_id = str(offer.get("id") or "").strip()
                    if offer_id and offer_city in requested_cities:
                        raw_by_id[offer_id] = map_offer_to_raw(offer)

                total_pages = max(1, int(payload.get("totalPages") or 1))
                if page >= total_pages:
                    break
                page += 1

    return list(raw_by_id.values())
