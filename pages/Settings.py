"""Streamlit settings page for app-level preferences."""

from __future__ import annotations

import streamlit as st

from src.config import get_app_paths
from src.models import AppSettings
from src.storage import StorageError, StorageManager
from src.ui.theme import inject_theme
from src.utils.logging_utils import configure_logging


def main() -> None:
    """Render the settings page."""
    configure_logging()
    st.set_page_config(
        page_title="Finance Dashboard Settings",
        page_icon=":gear:",
        layout="wide",
    )
    inject_theme()

    storage = StorageManager(paths=get_app_paths())

    try:
        storage.initialize()
        settings = storage.load_settings()
    except StorageError as exc:
        st.error(str(exc))
        st.stop()
        return

    st.title("Settings")
    st.caption("Adjust layout and local behavior without editing JSON files by hand.")

    with st.form("settings_form"):
        layout_col, cache_col = st.columns(2)
        with layout_col:
            grid_columns = st.selectbox(
                "Dashboard columns",
                options=[1, 2, 3, 4],
                index=[1, 2, 3, 4].index(settings.grid_columns),
                help="Controls how many instrument cards appear side by side on the dashboard.",
            )
            search_result_limit = st.number_input(
                "Search result limit",
                min_value=3,
                max_value=20,
                value=settings.search_result_limit,
                step=1,
                help="How many onvista matches to show when a search is ambiguous.",
            )
        with cache_col:
            cache_ttl_hours = st.number_input(
                "Cache TTL (hours)",
                min_value=1,
                max_value=168,
                value=settings.cache_ttl_hours,
                step=1,
                help="How long resolved instruments and chart data stay cached on disk.",
            )
            export_html_snapshot = st.checkbox(
                "Enable HTML snapshot export",
                value=settings.export_html_snapshot,
                help="Keeps the export preference ready for the upcoming export feature.",
            )

        saved = st.form_submit_button("Save Settings", width="content")

    if saved:
        updated_settings = AppSettings(
            selected_period=settings.selected_period,
            grid_columns=grid_columns,
            cache_ttl_hours=cache_ttl_hours,
            last_refresh_at=settings.last_refresh_at,
            export_html_snapshot=export_html_snapshot,
            search_result_limit=search_result_limit,
        )
        try:
            storage.save_settings(updated_settings)
        except StorageError as exc:
            st.error(str(exc))
        else:
            st.success("Settings saved.")
            st.rerun()

    st.markdown("### Current Values")
    info_1, info_2, info_3, info_4 = st.columns(4)
    info_1.metric("Grid columns", settings.grid_columns)
    info_2.metric("Cache TTL", f"{settings.cache_ttl_hours} h")
    info_3.metric("Search limit", settings.search_result_limit)
    info_4.metric("HTML export", "On" if settings.export_html_snapshot else "Off")


if __name__ == "__main__":
    main()
