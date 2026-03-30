"""Text parsing helpers for user input and provider normalization."""

from __future__ import annotations

import re

from src.utils.compat import StrEnum

ONVISTA_URL_PATTERN = re.compile(r"^https?://(?:www\.)?onvista\.de/.+", re.IGNORECASE)
ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
WKN_PATTERN = re.compile(r"^[A-Z0-9]{6}$")


class QueryKind(StrEnum):
    """Supported user query types."""

    URL = "url"
    ISIN = "isin"
    WKN = "wkn"
    NAME = "name"


def normalize_user_query(query: str) -> str:
    """Normalize one user-entered query."""
    return query.strip()


def detect_query_kind(query: str) -> QueryKind:
    """Detect how a user query should be interpreted."""
    normalized = normalize_user_query(query)
    uppercase = normalized.upper()

    if ONVISTA_URL_PATTERN.fullmatch(normalized):
        return QueryKind.URL
    if ISIN_PATTERN.fullmatch(uppercase):
        return QueryKind.ISIN
    if WKN_PATTERN.fullmatch(uppercase):
        return QueryKind.WKN
    return QueryKind.NAME


def normalize_instrument_type(display_type: str | None, entity_type: str | None) -> str | None:
    """Normalize instrument type labels into a small internal vocabulary."""
    mapping = {
        "AKTIE": "stock",
        "STOCK": "stock",
        "FONDS": "fund",
        "FUND": "fund",
        "ETF": "etf",
        "ETC": "etp",
        "ETN": "etp",
        "INDEX": "index",
    }

    for candidate in (display_type, entity_type):
        if not candidate:
            continue
        normalized = str(candidate).strip().upper()
        if normalized in mapping:
            return mapping[normalized]
        return normalized.lower()

    return None
