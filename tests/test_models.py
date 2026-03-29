"""Basic tests for typed dashboard models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models import AppSettings, ResolvedInstrument


def test_canonical_key_prefers_isin() -> None:
    instrument = ResolvedInstrument(
        display_name="Apple",
        isin="US0378331005",
        wkn="865985",
        onvista_url="https://www.onvista.de/aktien/Apple-Aktie-US0378331005",
        instrument_type="stock",
        currency="USD",
        source_label="Nasdaq",
    )

    assert instrument.canonical_key == "US0378331005"


def test_onvista_url_is_required() -> None:
    with pytest.raises(ValidationError):
        ResolvedInstrument(
            display_name="Broken",
            isin="US0378331005",
            wkn="865985",
            onvista_url="https://example.com/apple",
            instrument_type="stock",
            currency="USD",
            source_label="test",
        )


def test_app_settings_defaults_are_stable() -> None:
    settings = AppSettings()

    assert settings.grid_columns == 2
    assert settings.cache_ttl_hours == 24
    assert settings.search_result_limit == 8
