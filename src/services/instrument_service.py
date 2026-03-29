"""Business logic for watchlist resolution and mutation."""

from __future__ import annotations

from dataclasses import dataclass

from src.models import ResolvedInstrument, WatchlistItem
from src.providers.base import InstrumentNotFoundError, ProviderError
from src.providers.onvista_resolver import OnvistaResolver
from src.utils.text_utils import normalize_user_query


class InstrumentServiceError(RuntimeError):
    """Raised when a watchlist action cannot be completed."""


@dataclass
class MoveOperation:
    """Describe a watchlist reorder operation."""

    canonical_key: str
    offset: int


class InstrumentService:
    """Handle watchlist search, add, remove, and reorder actions."""

    def __init__(self, resolver: OnvistaResolver) -> None:
        self.resolver = resolver

    def search_candidates(self, query: str, max_results: int = 8) -> list[ResolvedInstrument]:
        """Search onvista for candidate instruments."""
        cleaned_query = normalize_user_query(query)
        if not cleaned_query:
            raise InstrumentServiceError("Enter an ISIN, WKN, name, or onvista URL first.")

        try:
            return self.resolver.search(cleaned_query, max_results=max_results)
        except InstrumentNotFoundError as exc:
            raise InstrumentServiceError(str(exc)) from exc
        except ProviderError as exc:
            raise InstrumentServiceError(
                "The instrument search is temporarily unavailable. Please try again in a moment."
            ) from exc

    def add_to_watchlist(
        self,
        watchlist: list[WatchlistItem],
        candidate: ResolvedInstrument,
    ) -> list[WatchlistItem]:
        """Resolve one candidate fully and append it to the watchlist."""
        detailed_instrument = self._resolve_candidate(candidate)
        new_item = WatchlistItem.model_validate(detailed_instrument.model_dump(mode="json"))
        existing_keys = {item.canonical_key for item in watchlist}

        if new_item.canonical_key in existing_keys:
            raise InstrumentServiceError(f'"{new_item.display_name}" is already in the watchlist.')

        return [*watchlist, new_item]

    def remove_from_watchlist(
        self,
        watchlist: list[WatchlistItem],
        canonical_key: str,
    ) -> list[WatchlistItem]:
        """Remove one instrument from the watchlist."""
        return [item for item in watchlist if item.canonical_key != canonical_key]

    def move_in_watchlist(
        self,
        watchlist: list[WatchlistItem],
        operation: MoveOperation,
    ) -> list[WatchlistItem]:
        """Move one watchlist item up or down."""
        current_index = self._find_index(watchlist, operation.canonical_key)
        target_index = current_index + operation.offset
        if current_index < 0 or target_index < 0 or target_index >= len(watchlist):
            return watchlist

        reordered = watchlist[:]
        reordered[current_index], reordered[target_index] = reordered[target_index], reordered[current_index]
        return reordered

    def _resolve_candidate(self, candidate: ResolvedInstrument) -> ResolvedInstrument:
        """Load the full detail page for a selected candidate."""
        try:
            return self.resolver.fetch_details(candidate.onvista_url)
        except ProviderError as exc:
            raise InstrumentServiceError(
                "The selected instrument could not be loaded in detail from onvista."
            ) from exc

    def _find_index(self, watchlist: list[WatchlistItem], canonical_key: str) -> int:
        """Return the index of one watchlist item."""
        for index, item in enumerate(watchlist):
            if item.canonical_key == canonical_key:
                return index
        return -1
