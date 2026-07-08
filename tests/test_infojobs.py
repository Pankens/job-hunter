from __future__ import annotations

import base64
import io
import json
from typing import Any

import pytest

from scripts.sources.infojobs import (
    InfoJobsClient,
    InfoJobsCredentials,
    InfoJobsCredentialsMissing,
    RSS_LIMITED_DESCRIPTION_WARNING,
    build_infojobs_feed_urls,
    fetch_infojobs_jobs,
    map_offer_to_raw,
    parse_infojobs_feed,
)


SAMPLE_API_OFFER = {
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

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Frontend Vue - Acme</title>
      <link>https://www.infojobs.net/valencia/frontend/of-i123</link>
      <guid>i123</guid>
      <pubDate>Wed, 01 Jul 2026 08:30:00 GMT</pubDate>
      <description><![CDATA[Oferta en Valencia para Vue, TypeScript, HTML y CSS.]]></description>
    </item>
  </channel>
</rss>
"""


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_rss_does_not_require_application_credentials():
    calls = 0

    def opener(_request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(SAMPLE_RSS.encode())

    jobs, stats = fetch_infojobs_jobs(
        {
            "cities": ["Valencia"],
            "searches": [{"name": "vue", "query": "Vue"}],
            "feed_url_templates": [
                "https://www.infojobs.net/trabajos.feed?keyword={query}&city={city}"
            ],
            "timeout_seconds": 5,
        },
        opener=opener,
    )

    assert calls == 1
    assert stats.source == "InfoJobs RSS"
    assert stats.feeds_consulted == 1
    assert len(jobs) == 1
    assert jobs[0]["source"] == "infojobs"


def test_builds_feed_urls_for_cities_and_queries():
    urls = build_infojobs_feed_urls(
        {
            "cities": ["Valencia", "Paterna"],
            "searches": [
                {"name": "general", "query": ""},
                {"name": "diseno-web", "query": "diseño web"},
            ],
            "feed_url_templates": [
                "https://www.infojobs.net/trabajos.feed?keyword={query}&city={city}"
            ],
        }
    )

    assert len(urls) == 4
    assert "city=Valencia" in urls[0]["url"]
    assert "dise%C3%B1o%20web" in urls[-1]["url"]


def test_parses_infojobs_rss_to_raw_contract():
    jobs = parse_infojobs_feed(
        SAMPLE_RSS.encode(),
        feed_url="https://www.infojobs.net/trabajos.feed?keyword=Vue&city=Valencia",
        configured_city="Valencia",
    )

    assert jobs[0]["title"] == "Frontend Vue - Acme"
    assert jobs[0]["company"] == "Acme"
    assert jobs[0]["city"] == "Valencia"
    assert jobs[0]["published_at"] == "Wed, 01 Jul 2026 08:30:00 GMT"
    assert jobs[0]["url"] == "https://www.infojobs.net/valencia/frontend/of-i123"
    assert jobs[0]["description"] == "Oferta en Valencia para Vue, TypeScript, HTML y CSS."
    assert RSS_LIMITED_DESCRIPTION_WARNING in jobs[0]["source_warnings"]


def test_fetches_rss_and_deduplicates_by_feed_id():
    calls = 0

    def opener(_request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(SAMPLE_RSS.encode())

    jobs, stats = fetch_infojobs_jobs(
        {
            "cities": ["Valencia"],
            "searches": [
                {"name": "general", "query": ""},
                {"name": "vue", "query": "Vue"},
            ],
            "feed_url_templates": [
                "https://www.infojobs.net/trabajos.feed?keyword={query}&city={city}"
            ],
            "timeout_seconds": 5,
        },
        opener=opener,
    )

    assert calls == 2
    assert stats.feeds_consulted == 2
    assert stats.offers_obtained == 1
    assert len(jobs) == 1
    assert jobs[0]["source_id"] == "i123"


def test_api_credentials_are_still_available_for_future_mode():
    with pytest.raises(InfoJobsCredentialsMissing):
        InfoJobsCredentials.from_environment({})


def test_future_api_client_uses_basic_auth_and_query_parameters():
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


def test_maps_future_api_offer_to_raw_contract():
    raw = map_offer_to_raw(SAMPLE_API_OFFER)

    assert raw["source"] == "infojobs"
    assert raw["source_id"] == "offer-123"
    assert raw["company"] == "Acme"
    assert raw["city"] == "Valencia"
    assert raw["salary_base_eur_month"] == 2000
    assert raw["published_at"] == SAMPLE_API_OFFER["published"]
    assert raw["source_warnings"]
