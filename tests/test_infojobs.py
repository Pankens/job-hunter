from __future__ import annotations

import base64
import io
import json
from typing import Any

import pytest

from scripts.sources.infojobs import (
    InfoJobsCredentials,
    InfoJobsCredentialsMissing,
    InfoJobsClient,
    fetch_infojobs_jobs,
    map_offer_to_raw,
)


SAMPLE_OFFER = {
    "id": "offer-123",
    "title": "Frontend Developer Vue",
    "city": "Valencia",
    "province": {"id": 46, "value": "Valencia/València"},
    "link": "https://www.infojobs.net/valencia/frontend/of-i123",
    "author": {"id": "company-1", "name": "Acme"},
    "published": "2026-07-01T08:30:00.000Z",
    "requirementMin": "Vue 3, TypeScript, HTML y CSS.",
    "salaryMin": {"id": 1, "value": "24.000 €"},
    "salaryPeriod": {"id": 1, "value": "Bruto/año"},
    "salaryDescription": "24.000 € - 30.000 € Bruto/año",
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_requires_application_credentials():
    with pytest.raises(InfoJobsCredentialsMissing):
        InfoJobsCredentials.from_environment({})


def test_client_uses_basic_auth_and_query_parameters():
    captured: dict[str, Any] = {}

    def opener(request, timeout):
        captured["authorization"] = request.get_header("Authorization")
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse(json.dumps({"offers": [], "totalPages": 1}).encode())

    client = InfoJobsClient(
        InfoJobsCredentials("client", "secret"),
        "https://api.infojobs.net/api/9/offer",
        timeout_seconds=9,
        opener=opener,
    )
    client.search({"city": "valencia", "q": "vue"})

    expected = base64.b64encode(b"client:secret").decode()
    assert captured["authorization"] == f"Basic {expected}"
    assert "city=valencia" in captured["url"]
    assert "q=vue" in captured["url"]
    assert captured["timeout"] == 9


def test_maps_infojobs_offer_to_raw_contract():
    raw = map_offer_to_raw(SAMPLE_OFFER)

    assert raw["source"] == "infojobs"
    assert raw["source_id"] == "offer-123"
    assert raw["company"] == "Acme"
    assert raw["city"] == "Valencia"
    assert raw["salary_base_eur_month"] == 2000
    assert raw["published_at"] == SAMPLE_OFFER["published"]
    assert raw["source_warnings"]


def test_missing_optional_infojobs_fields_do_not_break_mapping():
    raw = map_offer_to_raw(
        {
            "id": "minimal",
            "title": "Oferta sin detalle",
            "city": "Paterna",
            "author": {},
        }
    )

    assert raw["salary_base_eur_month"] is None
    assert raw["published_at"] is None
    assert raw["description"] == ""
    assert len(raw["source_warnings"]) >= 3


def test_fetches_searches_and_deduplicates_by_infojobs_id():
    calls = 0

    def opener(_request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(
            json.dumps({"offers": [SAMPLE_OFFER], "totalPages": 1}).encode()
        )

    settings = {
        "api_url": "https://api.infojobs.net/api/9/offer",
        "cities": ["Valencia"],
        "searches": [
            {"name": "general", "query": None},
            {"name": "skills", "query": "(Vue TypeScript)"},
        ],
        "since_date": "_7_DAYS",
        "max_results_per_page": 50,
        "max_pages_per_search": 2,
        "timeout_seconds": 5,
    }
    jobs = fetch_infojobs_jobs(
        settings,
        environment={
            "INFOJOBS_CLIENT_ID": "client",
            "INFOJOBS_CLIENT_SECRET": "secret",
        },
        opener=opener,
    )

    assert calls == 2
    assert len(jobs) == 1
    assert jobs[0]["source_id"] == "offer-123"
