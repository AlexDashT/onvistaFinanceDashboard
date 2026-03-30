"""Typed domain models for the finance dashboard."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.utils.compat import StrEnum

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
WKN_PATTERN = re.compile(r"^[A-Z0-9]{6}$")


class ChartPeriod(StrEnum):
    """Supported chart periods for the dashboard."""

    DAY_1 = "1D"
    WEEK_1 = "1W"
    MONTH_1 = "1M"
    MONTH_3 = "3M"
    YEAR_1 = "1Y"
    YEAR_3 = "3Y"
    YEAR_5 = "5Y"
    MAX = "MAX"


class DashboardModel(BaseModel):
    """Shared base model configuration."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResolvedInstrument(DashboardModel):
    """Normalized instrument metadata resolved from onvista."""

    display_name: str = Field(min_length=1)
    isin: str | None = None
    wkn: str | None = None
    onvista_url: str
    instrument_type: str | None = None
    currency: str | None = None
    source_label: str = "onvista"

    @field_validator("display_name", "instrument_type", "currency", "source_label", mode="before")
    @classmethod
    def _normalize_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("isin")
    @classmethod
    def _validate_isin(cls, value: str | None) -> str | None:
        if value is None:
            return value

        normalized = value.upper()
        if not ISIN_PATTERN.fullmatch(normalized):
            raise ValueError("ISIN must contain 12 alphanumeric characters in valid ISO format.")
        return normalized

    @field_validator("wkn")
    @classmethod
    def _validate_wkn(cls, value: str | None) -> str | None:
        if value is None:
            return value

        normalized = value.upper()
        if not WKN_PATTERN.fullmatch(normalized):
            raise ValueError("WKN must contain 6 alphanumeric characters.")
        return normalized

    @field_validator("onvista_url")
    @classmethod
    def _validate_onvista_url(cls, value: str) -> str:
        normalized = value.strip()
        if "onvista.de" not in normalized.lower():
            raise ValueError("The source URL must point to an onvista page.")
        return normalized

    @model_validator(mode="after")
    def _require_identifier(self) -> "ResolvedInstrument":
        if not any([self.isin, self.wkn, self.onvista_url]):
            raise ValueError("At least one canonical identifier must be available.")
        return self

    @property
    def canonical_key(self) -> str:
        """Return the preferred internal key for the instrument."""
        return self.isin or self.wkn or self.onvista_url


class WatchlistItem(ResolvedInstrument):
    """Persisted watchlist item."""


class AppSettings(DashboardModel):
    """User settings persisted to disk."""

    selected_period: ChartPeriod = ChartPeriod.YEAR_1
    grid_columns: int = Field(default=2, ge=1, le=4)
    cache_ttl_hours: int = Field(default=24, ge=1, le=168)
    last_refresh_at: datetime | None = None
    export_html_snapshot: bool = True
    search_result_limit: int = Field(default=8, ge=3, le=20)


class ChartPoint(DashboardModel):
    """One price point within a chart series."""

    timestamp: datetime
    price: float


class ChartSeries(DashboardModel):
    """Normalized chart series ready for plotting."""

    instrument_key: str
    period: ChartPeriod
    currency: str | None = None
    display_unit: str | None = None
    source_label: str = "onvista"
    data_origin: str = "onvista_simple_chart_history"
    last_updated_at: datetime | None = None
    points: list[ChartPoint] = Field(default_factory=list)


class ExportJobMetadata(DashboardModel):
    """Metadata describing one export operation."""

    export_id: str
    created_at: datetime
    output_dir: str
    selected_period: ChartPeriod
    file_names: list[str] = Field(default_factory=list)
