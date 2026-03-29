"""Sidebar UI for watchlist management."""

from __future__ import annotations

import streamlit as st

from src.config import AppPaths
from src.models import AppSettings, ResolvedInstrument, WatchlistItem
from src.services.instrument_service import InstrumentService, InstrumentServiceError, MoveOperation
from src.storage import StorageError, StorageManager

SEARCH_RESULTS_STATE_KEY = "watchlist_search_results"


def render_sidebar(
    paths: AppPaths,
    settings: AppSettings,
    watchlist: list[WatchlistItem],
    storage: StorageManager,
    instrument_service: InstrumentService,
) -> list[WatchlistItem]:
    """Render the sidebar and return the current watchlist."""
    with st.sidebar:
        _render_search_section(
            settings=settings,
            watchlist=watchlist,
            storage=storage,
            instrument_service=instrument_service,
        )
        st.divider()
        _render_watchlist_section(
            watchlist=watchlist,
            storage=storage,
            instrument_service=instrument_service,
        )
        st.divider()
        _render_current_state_section(settings, watchlist)
        st.divider()
        _render_workspace_section(paths)

    return storage.load_watchlist()


def _render_current_state_section(
    settings: AppSettings,
    watchlist: list[WatchlistItem],
) -> None:
    """Render the current application state."""
    st.subheader("Current State")
    st.metric("Instruments", len(watchlist))
    st.metric("Chart period", settings.selected_period.value)
    st.metric("Grid columns", settings.grid_columns)

    if settings.last_refresh_at:
        st.caption(f"Last refresh: {settings.last_refresh_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    else:
        st.caption("Last refresh: not yet triggered")


def _render_workspace_section(paths: AppPaths) -> None:
    """Render read-only workspace information."""
    st.subheader("Workspace")
    st.write(f"Watchlist file: `{paths.watchlist_file}`")
    st.write(f"Settings file: `{paths.settings_file}`")
    st.write(f"Cache directory: `{paths.cache_dir}`")


def _render_search_section(
    settings: AppSettings,
    watchlist: list[WatchlistItem],
    storage: StorageManager,
    instrument_service: InstrumentService,
) -> None:
    """Render the search and add-instrument workflow."""
    st.subheader("Add Instrument")
    with st.form("instrument_lookup_form", clear_on_submit=False):
        query = st.text_input(
            "Search onvista",
            placeholder="ISIN, WKN, free-text name, or onvista URL",
        )
        submitted = st.form_submit_button("Search", width="stretch")

    if submitted:
        try:
            results = instrument_service.search_candidates(
                query=query,
                max_results=settings.search_result_limit,
            )
        except InstrumentServiceError as exc:
            st.session_state[SEARCH_RESULTS_STATE_KEY] = []
            st.error(str(exc))
        else:
            st.session_state[SEARCH_RESULTS_STATE_KEY] = [item.model_dump(mode="json") for item in results]
            if len(results) == 1:
                st.success("1 matching instrument found.")
            else:
                st.success(f"{len(results)} matching instruments found.")

    raw_results = st.session_state.get(SEARCH_RESULTS_STATE_KEY, [])
    if not raw_results:
        st.caption("Search by ISIN, WKN, name, or direct onvista URL.")
        return

    results = [ResolvedInstrument.model_validate(item) for item in raw_results]
    selected_index = st.radio(
        "Matches",
        options=list(range(len(results))),
        format_func=lambda index: _format_candidate_label(results[index]),
    )
    selected_candidate = results[selected_index]

    st.caption(
        " | ".join(
            [
                f"Type: {selected_candidate.instrument_type or 'n/a'}",
                f"ISIN: {selected_candidate.isin or 'n/a'}",
                f"WKN: {selected_candidate.wkn or 'n/a'}",
                f"Source: {selected_candidate.source_label}",
            ]
        )
    )

    if st.button("Add Selected Instrument", width="stretch"):
        try:
            updated_watchlist = instrument_service.add_to_watchlist(watchlist, selected_candidate)
            storage.save_watchlist(updated_watchlist)
            st.session_state[SEARCH_RESULTS_STATE_KEY] = []
            st.rerun()
        except (InstrumentServiceError, StorageError) as exc:
            st.error(str(exc))


def _render_watchlist_section(
    watchlist: list[WatchlistItem],
    storage: StorageManager,
    instrument_service: InstrumentService,
) -> None:
    """Render watchlist management controls."""
    st.subheader("Watchlist")
    if not watchlist:
        st.caption("No instruments added yet.")
        return

    for index, item in enumerate(watchlist):
        with st.container(border=True):
            st.markdown(f"**{item.display_name}**")
            st.caption(
                " | ".join(
                    [
                        item.instrument_type or "instrument",
                        item.isin or item.wkn or "no identifier",
                        item.source_label,
                    ]
                )
            )

            move_up_col, move_down_col, remove_col = st.columns(3)
            with move_up_col:
                move_up = st.button(
                    "Up",
                    key=f"move_up_{item.canonical_key}",
                    disabled=index == 0,
                    width="stretch",
                )
            with move_down_col:
                move_down = st.button(
                    "Down",
                    key=f"move_down_{item.canonical_key}",
                    disabled=index == len(watchlist) - 1,
                    width="stretch",
                )
            with remove_col:
                remove = st.button(
                    "Remove",
                    key=f"remove_{item.canonical_key}",
                    width="stretch",
                )

            if move_up:
                _save_watchlist_and_rerun(
                    storage,
                    instrument_service.move_in_watchlist(
                        watchlist,
                        MoveOperation(canonical_key=item.canonical_key, offset=-1),
                    ),
                )
            if move_down:
                _save_watchlist_and_rerun(
                    storage,
                    instrument_service.move_in_watchlist(
                        watchlist,
                        MoveOperation(canonical_key=item.canonical_key, offset=1),
                    ),
                )
            if remove:
                _save_watchlist_and_rerun(
                    storage,
                    instrument_service.remove_from_watchlist(watchlist, item.canonical_key),
                )


def _save_watchlist_and_rerun(storage: StorageManager, watchlist: list[WatchlistItem]) -> None:
    """Persist the watchlist and rerun Streamlit."""
    storage.save_watchlist(watchlist)
    st.rerun()


def _format_candidate_label(candidate: ResolvedInstrument) -> str:
    """Return a readable label for one search result."""
    parts = [candidate.display_name]
    if candidate.instrument_type:
        parts.append(candidate.instrument_type)
    if candidate.isin:
        parts.append(candidate.isin)
    elif candidate.wkn:
        parts.append(candidate.wkn)
    return " | ".join(parts)
