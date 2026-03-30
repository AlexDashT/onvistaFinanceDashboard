"""Basic tests for chart service transformations."""

from __future__ import annotations

from datetime import datetime

from src.models import ChartPeriod, ChartPoint, ChartSeries, WatchlistItem
from src.services.chart_service import ChartService
from src.utils.compat import UTC


class _DummyHistoryProvider:
    """Minimal history provider stub for chart service tests."""

    def __init__(self, series: ChartSeries) -> None:
        self.series = series

    def fetch_chart_series(self, item: WatchlistItem, period: ChartPeriod) -> ChartSeries:
        return self.series


def test_chart_service_builds_dataframe_and_summary() -> None:
    series = ChartSeries(
        instrument_key="US0378331005",
        period=ChartPeriod.MONTH_1,
        currency="USD",
        display_unit="USD",
        points=[
            ChartPoint(timestamp=datetime(2026, 3, 1, tzinfo=UTC), price=100.0),
            ChartPoint(timestamp=datetime(2026, 3, 2, tzinfo=UTC), price=102.5),
            ChartPoint(timestamp=datetime(2026, 3, 3, tzinfo=UTC), price=105.0),
        ],
    )
    item = WatchlistItem(
        display_name="Apple",
        isin="US0378331005",
        wkn="865985",
        onvista_url="https://www.onvista.de/aktien/Apple-Aktie-US0378331005",
        instrument_type="stock",
        currency="USD",
        source_label="Nasdaq",
    )
    service = ChartService(history_provider=_DummyHistoryProvider(series))

    chart_view = service.build_chart_view(item=item, period=ChartPeriod.MONTH_1)
    frame = service.to_dataframe(series)

    assert len(frame) == 3
    assert chart_view.last_price == 105.0
    assert chart_view.absolute_change == 5.0
    assert round(chart_view.percent_change, 2) == 5.0
