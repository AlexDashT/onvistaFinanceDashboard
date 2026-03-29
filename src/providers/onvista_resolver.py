"""Resolve instruments from onvista search pages and detail pages."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup
import httpx
from rapidfuzz import fuzz
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.models import ResolvedInstrument
from src.providers.base import (
    InstrumentNotFoundError,
    ProviderNetworkError,
    ProviderParsingError,
)
from src.services.cache_service import CacheService
from src.utils.logging_utils import get_logger
from src.utils.text_utils import (
    QueryKind,
    detect_query_kind,
    normalize_instrument_type,
    normalize_user_query,
)

logger = get_logger(__name__)


class OnvistaResolver:
    """Resolve onvista instruments from identifiers, names, or URLs."""

    BASE_URL = "https://www.onvista.de"
    SEARCH_URL = f"{BASE_URL}/suche"
    ALLOWED_ENTITY_TYPES = {"STOCK", "FUND", "ETF", "ETC", "ETN", "INDEX"}

    def __init__(
        self,
        cache_service: CacheService,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.cache_service = cache_service
        self._client = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FinanceDashboard/1.0"},
            follow_redirects=True,
            timeout=timeout_seconds,
        )

    def search(self, query: str, max_results: int = 8) -> list[ResolvedInstrument]:
        """Return matching instruments for a user query."""
        normalized_query = normalize_user_query(query)
        query_kind = detect_query_kind(normalized_query)
        cache_key = f"onvista-search::{normalized_query.lower()}::{max_results}"
        cached_payload = self.cache_service.get_json(cache_key)

        if cached_payload is not None:
            return [ResolvedInstrument.model_validate(item) for item in cached_payload]

        if query_kind is QueryKind.URL:
            result = [self.fetch_details(normalized_query)]
            self._store_search_cache(cache_key, result)
            return result

        search_url = f"{self.SEARCH_URL}/{quote(normalized_query)}"
        response = self._get(search_url)
        final_url = str(response.url)

        if self._is_instrument_page(final_url):
            result = [self._parse_instrument_page(response.text, final_url)]
            self._store_search_cache(cache_key, result)
            return result

        results = self._parse_search_results(response.text, normalized_query, query_kind)
        if not results:
            raise InstrumentNotFoundError(
                f'No matching instrument was found for "{normalized_query}". Try a more specific name, ISIN, or WKN.'
            )

        limited_results = results[:max_results]
        self._store_search_cache(cache_key, limited_results)
        return limited_results

    def fetch_details(self, onvista_url: str) -> ResolvedInstrument:
        """Resolve a single onvista detail page into normalized metadata."""
        cache_key = f"onvista-detail::{onvista_url}"
        cached_payload = self.cache_service.get_json(cache_key)

        if cached_payload is not None:
            return ResolvedInstrument.model_validate(cached_payload)

        response = self._get(onvista_url)
        instrument = self._parse_instrument_page(response.text, str(response.url))
        self.cache_service.set_json(cache_key, instrument.model_dump(mode="json"))
        return instrument

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, ProviderNetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        reraise=True,
    )
    def _get(self, url: str) -> httpx.Response:
        """Fetch one URL from onvista with retries."""
        try:
            response = self._client.get(url)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            logger.warning("onvista request failed for %s: %s", url, exc)
            raise ProviderNetworkError("The onvista page could not be loaded right now.") from exc

    def _parse_instrument_page(self, html: str, page_url: str) -> ResolvedInstrument:
        """Parse a detail page into a normalized instrument model."""
        next_data = self._extract_next_data(html)
        snapshot = next_data.get("props", {}).get("pageProps", {}).get("data", {}).get("snapshot")
        if not isinstance(snapshot, dict):
            raise ProviderParsingError("The onvista detail page structure changed and could not be read.")

        instrument = snapshot.get("instrument") or {}
        quote = snapshot.get("quote") or {}

        return ResolvedInstrument(
            display_name=instrument.get("tinyName") or instrument.get("name") or "Unknown instrument",
            isin=instrument.get("isin"),
            wkn=instrument.get("wkn"),
            onvista_url=self._absolute_url(instrument.get("urls", {}).get("WEBSITE") or page_url),
            instrument_type=normalize_instrument_type(
                display_type=instrument.get("displayType"),
                entity_type=instrument.get("entityType"),
            ),
            currency=quote.get("isoCurrency"),
            source_label=self._extract_source_label(quote) or "onvista",
        )

    def _parse_search_results(
        self,
        html: str,
        query: str,
        query_kind: QueryKind,
    ) -> list[ResolvedInstrument]:
        """Parse the onvista search page and rank the candidates."""
        next_data = self._extract_next_data(html)
        facets = next_data.get("props", {}).get("pageProps", {}).get("facets", [])
        results: list[ResolvedInstrument] = []
        seen_keys: set[str] = set()

        for facet in facets:
            if not isinstance(facet, dict):
                continue

            for item in facet.get("results") or []:
                if not isinstance(item, dict):
                    continue

                candidate = self._result_to_instrument(item)
                if candidate is None:
                    continue

                if candidate.canonical_key in seen_keys:
                    continue

                seen_keys.add(candidate.canonical_key)
                results.append(candidate)

        return sorted(results, key=lambda item: self._rank_candidate(query, item, query_kind), reverse=True)

    def _result_to_instrument(self, item: dict[str, Any]) -> ResolvedInstrument | None:
        """Convert one raw search result into a normalized instrument."""
        entity_type = str(item.get("entityType") or "").upper()
        if entity_type and entity_type not in self.ALLOWED_ENTITY_TYPES:
            return None

        onvista_url = self._absolute_url(item.get("urls", {}).get("WEBSITE"))
        if onvista_url == self.BASE_URL:
            return None

        return ResolvedInstrument(
            display_name=item.get("tinyName") or item.get("name") or "Unknown instrument",
            isin=item.get("isin"),
            wkn=item.get("wkn"),
            onvista_url=onvista_url,
            instrument_type=normalize_instrument_type(
                display_type=item.get("displayType"),
                entity_type=item.get("entityType"),
            ),
            currency=item.get("isoCurrency"),
            source_label="onvista",
        )

    def _rank_candidate(self, query: str, item: ResolvedInstrument, query_kind: QueryKind) -> int:
        """Score a candidate so the most relevant matches appear first."""
        normalized_query = query.lower()
        haystack = " ".join(
            part for part in [item.display_name, item.isin or "", item.wkn or "", item.instrument_type or ""] if part
        ).lower()
        base_score = int(fuzz.WRatio(normalized_query, haystack))

        if query_kind is QueryKind.ISIN and item.isin == query.upper():
            return 1_000

        if query_kind is QueryKind.WKN and item.wkn == query.upper():
            return 950

        if item.display_name.lower() == normalized_query:
            base_score += 150
        elif item.display_name.lower().startswith(normalized_query):
            base_score += 100

        if item.instrument_type in {"stock", "fund", "etf", "etp"}:
            base_score += 20

        return base_score

    def _extract_next_data(self, html: str) -> dict[str, Any]:
        """Extract Next.js page data from an onvista HTML response."""
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script is None or not script.string:
            raise ProviderParsingError(
                "The onvista page structure changed. The resolver could not find structured page data."
            )

        # onvista currently exposes the most reliable metadata in this script.
        try:
            parsed = json.loads(script.string)
        except json.JSONDecodeError as exc:
            raise ProviderParsingError("The onvista page data could not be parsed.") from exc

        if not isinstance(parsed, dict):
            raise ProviderParsingError("The onvista page data was not in the expected format.")
        return parsed

    def _extract_source_label(self, quote: dict[str, Any]) -> str | None:
        """Return the most helpful source label visible on the onvista page."""
        market = quote.get("market") or {}
        return market.get("name") or market.get("nameExchange") or quote.get("codeQualityPrice")

    def _absolute_url(self, url: str | None) -> str:
        """Return an absolute onvista URL."""
        if not url:
            return self.BASE_URL
        return urljoin(f"{self.BASE_URL}/", url)

    def _is_instrument_page(self, url: str) -> bool:
        """Return true when a URL points to an instrument detail page."""
        return url.startswith(self.BASE_URL) and "/suche/" not in url

    def _store_search_cache(self, cache_key: str, results: list[ResolvedInstrument]) -> None:
        """Persist cached search candidates to disk."""
        self.cache_service.set_json(
            cache_key,
            [item.model_dump(mode="json") for item in results],
        )
