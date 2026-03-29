"""Basic tests for local JSON persistence."""

from __future__ import annotations

from pathlib import Path

from src.config import AppPaths
from src.models import AppSettings, WatchlistItem
from src.storage import StorageManager


def test_storage_initializes_default_files(tmp_path: Path) -> None:
    paths = AppPaths(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "data" / "cache",
        exports_dir=tmp_path / "data" / "exports",
        watchlist_file=tmp_path / "data" / "watchlist.json",
        settings_file=tmp_path / "data" / "settings.json",
    )
    storage = StorageManager(paths=paths)

    storage.initialize()

    assert paths.watchlist_file.exists()
    assert paths.settings_file.exists()
    assert storage.load_watchlist() == []
    assert isinstance(storage.load_settings(), AppSettings)


def test_storage_round_trips_watchlist_items(tmp_path: Path) -> None:
    paths = AppPaths(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "data" / "cache",
        exports_dir=tmp_path / "data" / "exports",
        watchlist_file=tmp_path / "data" / "watchlist.json",
        settings_file=tmp_path / "data" / "settings.json",
    )
    storage = StorageManager(paths=paths)
    storage.initialize()

    items = [
        WatchlistItem(
            display_name="Apple",
            isin="US0378331005",
            wkn="865985",
            onvista_url="https://www.onvista.de/aktien/Apple-Aktie-US0378331005",
            instrument_type="stock",
            currency="USD",
            source_label="Nasdaq",
        )
    ]

    storage.save_watchlist(items)

    loaded_items = storage.load_watchlist()
    assert len(loaded_items) == 1
    assert loaded_items[0].display_name == "Apple"
