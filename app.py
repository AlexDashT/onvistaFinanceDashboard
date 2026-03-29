"""Streamlit entry point for the finance dashboard."""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from src.config import get_app_paths
from src.models import AppSettings, ChartPeriod
from src.providers.onvista_history_provider import OnvistaHistoryProvider
from src.providers.onvista_resolver import OnvistaResolver
from src.services.cache_service import CacheService
from src.services.chart_service import ChartService
from src.services.instrument_service import InstrumentService
from src.storage import StorageError, StorageManager
from src.ui.charts import render_dashboard_charts
from src.ui.sidebar import render_sidebar
from src.ui.theme import inject_theme
from src.utils.logging_utils import configure_logging


def _save_settings_if_changed(
    storage: StorageManager,
    settings: AppSettings,
    selected_period: str,
) -> AppSettings:
    """Persist changed UI settings and return the current settings object."""
    updated_settings = settings.model_copy(
        update={
            "selected_period": ChartPeriod(selected_period),
        }
    )

    if updated_settings != settings:
        storage.save_settings(updated_settings)
        return updated_settings

    return settings


def main() -> None:
    """Run the Streamlit dashboard shell."""
    configure_logging()
    st.set_page_config(
        page_title="Finance Dashboard",
        page_icon=":bar_chart:",
        layout="wide",
    )
    inject_theme()

    paths = get_app_paths()
    storage = StorageManager(paths=paths)

    try:
        storage.initialize()
        settings = storage.load_settings()
        watchlist = storage.load_watchlist()
    except StorageError as exc:
        st.error(str(exc))
        st.stop()
        return

    cache_service = CacheService(cache_dir=paths.cache_dir, ttl_hours=settings.cache_ttl_hours)
    resolver = OnvistaResolver(cache_service=cache_service)
    history_provider = OnvistaHistoryProvider(cache_service=cache_service)
    chart_service = ChartService(history_provider=history_provider)
    instrument_service = InstrumentService(resolver=resolver)

    st.title("Finance Dashboard")
    st.caption("Local-first watchlist for onvista instruments with persisted settings.")

    toolbar_left, toolbar_right = st.columns([1, 3])
    with toolbar_left:
        selected_period = st.selectbox(
            "Period",
            options=[period.value for period in ChartPeriod],
            index=list(ChartPeriod).index(settings.selected_period),
        )
    with toolbar_right:
        if st.button("Refresh", width="content"):
            settings = settings.model_copy(update={"last_refresh_at": datetime.now(timezone.utc)})
            storage.save_settings(settings)
            st.success("Refresh time updated.")

    settings = _save_settings_if_changed(
        storage=storage,
        settings=settings,
        selected_period=selected_period,
    )
    cache_service.ttl_hours = settings.cache_ttl_hours

    watchlist = render_sidebar(
        paths=paths,
        settings=settings,
        watchlist=watchlist,
        storage=storage,
        instrument_service=instrument_service,
    )

    info_1, info_2, info_3 = st.columns(3)
    info_1.metric("Watchlist size", len(watchlist))
    info_2.metric("Default columns", settings.grid_columns)
    info_3.metric("Cache TTL (hours)", settings.cache_ttl_hours)

    render_dashboard_charts(
        items=watchlist,
        settings=settings,
        chart_service=chart_service,
    )


if __name__ == "__main__":
    main()
