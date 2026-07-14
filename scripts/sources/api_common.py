"""Helpers for JSON job-board APIs."""

from __future__ import annotations

import re
from html import unescape
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "job-hunter/0.1 (+https://github.com/Pankens/job-hunter)",
    "Accept": "application/json",
}


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def html_to_text(value: Any) -> str:
    html = unescape(str(value or ""))
    if not html:
        return ""
    return compact_text(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))


def fetch_json(url: str, timeout_seconds: int = 20) -> tuple[int, Any]:
    response = requests.get(url, headers=HEADERS, timeout=timeout_seconds)
    response.raise_for_status()
    return response.status_code, response.json()


def timestamp_ms_to_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        seconds = int(value) / 1000
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_to_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
