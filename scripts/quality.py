"""Barreras de calidad antes de publicar una oferta como valida."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from scripts.normalize import comparable_text


GENERIC_TITLES = {
    "barcelona",
    "madrid",
    "valencia",
    "dependiente",
    "cajero",
    "reponedor",
    "limpieza",
    "hosteleria",
    "programador",
    "desarrollador",
    "frontend",
    "backend",
    "ofertas de empleo",
    "ofertas de trabajo",
    "trabajo",
}

NAVIGATION_URL_HINTS = (
    "/jobs?q=",
    "/ofertas-trabajo/",
    "/trabajos/",
    "/search",
    "/categor",
    "/tag/",
)

MIN_DESCRIPTION_CHARS = 80
MIN_DESCRIPTION_WORDS = 12


def _has_http_url(value: Any) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_remote(job: dict[str, Any]) -> bool:
    text = comparable_text(" ".join(str(job.get(field, "")) for field in ("city", "location")))
    return bool(job.get("remote")) or "remote" in text or "teletrabajo" in text


def quality_reject_reasons(job: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    title = str(job.get("title") or "").strip()
    title_key = comparable_text(title)
    company = str(job.get("company") or "").strip()
    description = str(job.get("description") or "").strip()
    url = str(job.get("url") or "").strip()
    parsed_path = urlparse(url).path.lower()

    if len(title) < 4 or title_key in GENERIC_TITLES:
        reasons.append("Control de calidad: titulo de puesto no identificable")
    if not company:
        reasons.append("Control de calidad: empresa no identificable")
    if not _has_http_url(url):
        reasons.append("Control de calidad: URL ausente o no valida")
    elif not job.get("directUrl") or any(hint in parsed_path for hint in NAVIGATION_URL_HINTS):
        reasons.append("Control de calidad: URL no parece apuntar a una oferta individual")
    if not (str(job.get("city") or "").strip() or str(job.get("location") or "").strip() or _is_remote(job)):
        reasons.append("Control de calidad: ubicacion o modalidad remota no indicada")

    words = [word for word in description.split() if word.strip()]
    if len(description) < MIN_DESCRIPTION_CHARS or len(words) < MIN_DESCRIPTION_WORDS:
        reasons.append("Control de calidad: descripcion insuficiente para filtrar")

    return reasons
