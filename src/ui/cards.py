"""Dashboard card rendering helpers."""

from __future__ import annotations

import html

import streamlit as st

from src.models import WatchlistItem


def render_dashboard_cards(items: list[WatchlistItem]) -> None:
    """Render the current watchlist on the main dashboard."""
    st.markdown("### Dashboard")
    if not items:
        render_empty_state()
        return

    for item in items:
        render_watchlist_card(item)


def render_empty_state() -> None:
    """Render the dashboard empty state."""
    st.markdown(
        """
        <div class="fd-empty-state">
          <h3>Your watchlist is empty</h3>
          <p>
            Use the sidebar to search onvista by ISIN, WKN, name, or direct URL.
            The selected instruments are saved automatically to the local JSON watchlist.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_watchlist_card(item: WatchlistItem) -> None:
    """Render one summary card for a watchlist item."""
    safe_name = html.escape(item.display_name)
    safe_type = html.escape(item.instrument_type or "instrument")
    safe_currency = html.escape(item.currency or "n/a")
    safe_source = html.escape(item.source_label)
    safe_url = html.escape(item.onvista_url, quote=True)

    st.markdown(
        f"""
        <div class="fd-card">
          <div class="fd-card__header">
            <div>
              <div class="fd-card__title">{safe_name}</div>
              <div class="fd-card__meta">{safe_type} | {safe_currency}</div>
            </div>
            <span class="fd-badge">{safe_source}</span>
          </div>
          <div class="fd-card__body">
            <div><strong>ISIN:</strong> {item.isin or "n/a"}</div>
            <div><strong>WKN:</strong> {item.wkn or "n/a"}</div>
            <div><strong>Canonical key:</strong> {item.canonical_key}</div>
            <div><strong>Source URL:</strong> <a href="{safe_url}" target="_blank">Open onvista</a></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
