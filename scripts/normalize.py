"""Normalización de ofertas de distintas fuentes a un contrato común."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def comparable_text(value: Any) -> str:
    """Devuelve texto en minúsculas y sin tildes para comparar reglas."""
    text = unicodedata.normalize("NFKD", _clean(value).lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _published_at(raw: dict[str, Any], generated_at: datetime) -> datetime:
    value = raw.get("published_at")
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(str(value))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except (TypeError, ValueError):
                pass
    return generated_at - timedelta(hours=float(raw.get("published_hours_ago", 0)))


def normalize_job(raw: dict[str, Any], generated_at: datetime) -> dict[str, Any]:
    source = comparable_text(raw.get("source")) or "unknown"
    source_id = _clean(raw.get("source_id"))
    stable_seed = "|".join(
        [source, source_id, comparable_text(raw.get("title")), comparable_text(raw.get("company"))]
    )
    job_id = f"{source}-{hashlib.sha1(stable_seed.encode()).hexdigest()[:12]}"
    published_at = _published_at(raw, generated_at)

    return {
        "id": job_id,
        "source": source,
        "sourceId": source_id,
        "title": _clean(raw.get("title")),
        "company": _clean(raw.get("company")) or "Empresa no indicada",
        "city": _clean(raw.get("city")),
        "location": _clean(raw.get("location")),
        "description": _clean(raw.get("description")),
        "requirements": _clean(raw.get("requirements")),
        "requiredLanguages": [_clean(item).lower() for item in raw.get("required_languages", [])],
        "salaryText": _clean(raw.get("salary_text")),
        "salaryBaseEurMonth": raw.get("salary_base_eur_month"),
        "hasCommission": bool(raw.get("has_commission", False)),
        "publishedAt": published_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "url": _clean(raw.get("url")) or "#",
        "sourceWarnings": [
            _clean(warning) for warning in raw.get("source_warnings", []) if _clean(warning)
        ],
    }


def normalize_jobs(raw_jobs: list[dict[str, Any]], generated_at: datetime) -> list[dict[str, Any]]:
    return [normalize_job(raw, generated_at) for raw in raw_jobs]
