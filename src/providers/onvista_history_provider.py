"""Load historical price series for local chart rendering."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from bs4 import BeautifulSoup
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.models import ChartPeriod, ChartPoint, ChartSeries, WatchlistItem
from src.providers.base import ChartDataUnavailableError, ProviderNetworkError, ProviderParsingError
from src.services.cache_service import CacheService
from src.utils.compat import UTC
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


class OnvistaHistoryProvider:
    """Resolve onvista chart metadata and fetch price history."""

    BASE_URL = "https://www.onvista.de"
    API_BASE_URL = "https://api.onvista.de/api/v1/instruments"
    PERIOD_MAP: dict[ChartPeriod, str] = {
        ChartPeriod.DAY_1: "D1",
        ChartPeriod.WEEK_1: "W1",
        ChartPeriod.MONTH_1: "M1",
        ChartPeriod.MONTH_3: "M3",
        ChartPeriod.YEAR_1: "Y1",
        ChartPeriod.YEAR_3: "Y3",
        ChartPeriod.YEAR_5: "Y5",
        ChartPeriod.MAX: "MAX",
    }

    def __init__(self, cache_service: CacheService, timeout_seconds: float = 20.0) -> None:
        self.cache_service = cache_service
        self._client = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FinanceDashboard/1.0"},
            follow_redirects=True,
            timeout=timeout_seconds,
        )

    def fetch_chart_series(self, item: WatchlistItem, period: ChartPeriod) -> ChartSeries:
        """Return a normalized chart series for one watchlist item."""
        cache_key = f"chart-series::{item.canonical_key}::{period.value}"
        cached_payload = self.cache_service.get_json(cache_key)
        if cached_payload is not None:
            return ChartSeries.model_validate(cached_payload)

        context = self._load_chart_context(item)
        range_value = self.PERIOD_MAP[period]
        available_ranges = context.get("available_ranges", [])
        if available_ranges and range_value not in available_ranges:
            raise ChartDataUnavailableError(
                f'{item.display_name} does not expose the selected {period.value} range on the current onvista page.'
            )

        endpoint = (
            f"{self.API_BASE_URL}/{context['entity_type']}/{context['entity_value']}/simple_chart_history"
        )
        payload = self._get_json(
            endpoint,
            params={
                "chartType": "PRICE",
                "idNotation": context["id_notation"],
                "range": range_value,
                "withEarnings": "false",
            },
        )
        series = self._payload_to_chart_series(item=item, period=period, payload=payload)
        self.cache_service.set_json(cache_key, series.model_dump(mode="json"))
        return series

    def _load_chart_context(self, item: WatchlistItem) -> dict[str, Any]:
        """Load chart context from the instrument detail page."""
        cache_key = f"chart-context::{item.canonical_key}"
        cached_payload = self.cache_service.get_json(cache_key)
        if isinstance(cached_payload, dict):
            return cached_payload

        payload = self._get_page_payload(item.onvista_url)
        snapshot = payload.get("props", {}).get("pageProps", {}).get("data", {}).get("snapshot")
        if not isinstance(snapshot, dict):
            raise ChartDataUnavailableError(
                f"No chart snapshot data was found on the onvista page for {item.display_name}."
            )

        instrument = snapshot.get("instrument") or {}
        chart = snapshot.get("chart") or {}
        if not instrument or not chart:
            raise ChartDataUnavailableError(
                f"No chart configuration is currently available on the onvista page for {item.display_name}."
            )

        entity_type = str(instrument.get("entityType") or "").upper()
        entity_value = instrument.get("entityValue")
        id_notation = chart.get("idNotation")
        if not entity_type or entity_value is None or id_notation is None:
            raise ProviderParsingError("The onvista chart metadata could not be read from the detail page.")

        context = {
            "entity_type": entity_type,
            "entity_value": str(entity_value),
            "id_notation": str(id_notation),
            "available_ranges": chart.get("ranges") or [],
        }
        self.cache_service.set_json(cache_key, context)
        return context

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, ProviderNetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        reraise=True,
    )
    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        """Fetch one JSON response from onvista."""
        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("onvista chart request failed for %s: %s", url, exc)
            raise ProviderNetworkError("The onvista chart data could not be loaded right now.") from exc
        except json.JSONDecodeError as exc:
            raise ProviderParsingError("The onvista chart API returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise ProviderParsingError("The onvista chart API returned an unexpected response.")
        return payload

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, ProviderNetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        reraise=True,
    )
    def _get_page_payload(self, url: str) -> dict[str, Any]:
        """Fetch Next.js page data from one onvista detail page."""
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("onvista detail page request failed for %s: %s", url, exc)
            raise ProviderNetworkError("The onvista detail page could not be loaded right now.") from exc

        soup = BeautifulSoup(response.text, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script is None or not script.string:
            raise ProviderParsingError("The onvista detail page no longer exposes readable page data.")

        # This relies on current onvista Next.js page data because it is the
        # most direct place to read the notation and entity identifiers used by
        # the visible chart pages and price-history table.
        try:
            payload = json.loads(script.string)
        except json.JSONDecodeError as exc:
            raise ProviderParsingError("The onvista detail page data could not be parsed.") from exc

        if not isinstance(payload, dict):
            raise ProviderParsingError("The onvista detail page data was not in the expected format.")
        return payload

    def _payload_to_chart_series(
        self,
        item: WatchlistItem,
        period: ChartPeriod,
        payload: dict[str, Any],
    ) -> ChartSeries:
        """Convert a raw API payload into a typed chart series."""
        timestamps = payload.get("datetimeTick") or []
        prices = payload.get("tick") or []
        if not timestamps or not prices:
            raise ChartDataUnavailableError(
                f"onvista returned no chart values for {item.display_name} in the selected {period.value} range."
            )

        if len(timestamps) != len(prices):
            raise ProviderParsingError("The onvista chart response contained mismatched timestamps and values.")

        points = [
            ChartPoint(
                timestamp=datetime.fromtimestamp(timestamp / 1000, tz=UTC),
                price=float(price),
            )
            for timestamp, price in zip(timestamps, prices, strict=True)
        ]

        return ChartSeries(
            instrument_key=item.canonical_key,
            period=period,
            currency=payload.get("isoCurrency") or item.currency,
            display_unit=payload.get("displayUnit") or item.currency,
            source_label=item.source_label,
            last_updated_at=datetime.now(tz=UTC),
            points=points,
        )
