"""Dashboard chart rendering helpers."""

from __future__ import annotations

from itertools import batched

import streamlit as st

from src.models import AppSettings, WatchlistItem
from src.services.chart_service import ChartService, ChartServiceError, ChartViewModel, format_price_display
from src.ui.cards import render_empty_state


def render_dashboard_charts(
    items: list[WatchlistItem],
    settings: AppSettings,
    chart_service: ChartService,
) -> None:
    """Render the dashboard grid with local charts."""
    st.markdown("### Dashboard")
    if not items:
        render_empty_state()
        return

    for row_items in batched(items, settings.grid_columns):
        columns = st.columns(len(row_items))
        for column, item in zip(columns, row_items, strict=True):
            with column:
                _render_chart_card(item=item, settings=settings, chart_service=chart_service)


def _render_chart_card(
    item: WatchlistItem,
    settings: AppSettings,
    chart_service: ChartService,
) -> None:
    """Render one chart card with inline error handling."""
    with st.container(border=True):
        st.markdown(f"**{item.display_name}**")
        st.caption(
            " | ".join(
                [
                    item.instrument_type or "instrument",
                    item.currency or "n/a",
                    item.source_label,
                    "price chart",
                ]
            )
        )

        try:
            with st.spinner("Loading chart..."):
                chart_view = chart_service.build_chart_view(item=item, period=settings.selected_period)
        except ChartServiceError as exc:
            st.error(str(exc))
            st.link_button("Open onvista", item.onvista_url, width="stretch")
            return

        st.plotly_chart(
            chart_view.figure,
            width="stretch",
            config={"displayModeBar": False, "responsive": True},
        )
        _render_chart_summary(chart_view, item)
        st.link_button("Open onvista", item.onvista_url, width="stretch")


def _render_chart_summary(chart_view: ChartViewModel, item: WatchlistItem) -> None:
    """Render summary values under one chart."""
    change_prefix = "+" if chart_view.absolute_change >= 0 else ""
    st.caption(
        " | ".join(
            [
                f"Last: {format_price_display(chart_view.last_price, chart_view.series.display_unit or item.currency)}",
                f"Change: {change_prefix}{format_price_display(abs(chart_view.absolute_change), chart_view.series.display_unit or item.currency)}",
                f"{change_prefix}{chart_view.percent_change:.2f}%",
                f"Points: {len(chart_view.series.points)}",
            ]
        )
    )
    if chart_view.series.last_updated_at:
        st.caption(
            f"Chart refreshed: {chart_view.series.last_updated_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
