"""Application configuration and project paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.models import AppSettings


@dataclass(frozen=True)
class AppPaths:
    """Resolved filesystem paths used by the application."""

    project_root: Path
    data_dir: Path
    cache_dir: Path
    exports_dir: Path
    watchlist_file: Path
    settings_file: Path


def get_app_paths() -> AppPaths:
    """Return the canonical project paths."""
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    cache_dir = data_dir / "cache"
    exports_dir = data_dir / "exports"

    return AppPaths(
        project_root=project_root,
        data_dir=data_dir,
        cache_dir=cache_dir,
        exports_dir=exports_dir,
        watchlist_file=data_dir / "watchlist.json",
        settings_file=data_dir / "settings.json",
    )


def get_default_settings() -> AppSettings:
    """Return the default settings stored on first run."""
    return AppSettings()

