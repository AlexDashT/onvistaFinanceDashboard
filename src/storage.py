"""Local JSON storage helpers for the finance dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from src.config import AppPaths, get_app_paths, get_default_settings
from src.models import AppSettings, WatchlistItem


class StorageError(RuntimeError):
    """Raised when persistent storage cannot be loaded or saved."""


class StorageManager:
    """Read and write local JSON files for app state."""

    def __init__(self, paths: AppPaths | None = None) -> None:
        self.paths = paths or get_app_paths()
        self._watchlist_adapter = TypeAdapter(list[WatchlistItem])

    def initialize(self) -> None:
        """Create required directories and default files on first run."""
        for directory in (self.paths.data_dir, self.paths.cache_dir, self.paths.exports_dir):
            directory.mkdir(parents=True, exist_ok=True)

        if not self.paths.watchlist_file.exists():
            self.save_watchlist([])

        if not self.paths.settings_file.exists():
            self.save_settings(get_default_settings())

    def load_watchlist(self) -> list[WatchlistItem]:
        """Load the persisted watchlist from disk."""
        payload = self._read_json_file(self.paths.watchlist_file)

        try:
            return self._watchlist_adapter.validate_python(payload)
        except ValidationError as exc:
            raise StorageError(
                f"Watchlist file is invalid: {self.paths.watchlist_file}"
            ) from exc

    def save_watchlist(self, items: list[WatchlistItem]) -> None:
        """Persist the current watchlist using an atomic file write."""
        serialized = [item.model_dump(mode="json") for item in items]
        self._write_json_file(self.paths.watchlist_file, serialized)

    def load_settings(self) -> AppSettings:
        """Load persisted app settings from disk."""
        payload = self._read_json_file(self.paths.settings_file)
        normalized_payload = self._normalize_settings_payload(payload)

        try:
            settings = AppSettings.model_validate(normalized_payload)
        except ValidationError as exc:
            raise StorageError(
                f"Settings file is invalid: {self.paths.settings_file}"
            ) from exc

        if normalized_payload != payload:
            self.save_settings(settings)

        return settings

    def save_settings(self, settings: AppSettings) -> None:
        """Persist the current settings using an atomic file write."""
        self._write_json_file(self.paths.settings_file, settings.model_dump(mode="json"))

    def _normalize_settings_payload(self, payload: Any) -> dict[str, Any]:
        """Migrate legacy settings keys before validation."""
        if not isinstance(payload, dict):
            return payload

        normalized_payload = dict(payload)
        normalized_payload.pop("chart_mode", None)

        default_payload = get_default_settings().model_dump(mode="json")
        for key, value in default_payload.items():
            normalized_payload.setdefault(key, value)

        return normalized_payload

    def _read_json_file(self, path: Path) -> Any:
        """Read JSON content from disk."""
        try:
            with path.open("r", encoding="utf-8") as file_handle:
                return json.load(file_handle)
        except FileNotFoundError as exc:
            raise StorageError(f"Missing storage file: {path}") from exc
        except json.JSONDecodeError as exc:
            raise StorageError(f"Invalid JSON in storage file: {path}") from exc
        except OSError as exc:
            raise StorageError(f"Could not read storage file: {path}") from exc

    def _write_json_file(self, path: Path, payload: Any) -> None:
        """Write JSON content to disk via a temporary file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")

        try:
            with temporary_path.open("w", encoding="utf-8") as file_handle:
                json.dump(payload, file_handle, indent=2, ensure_ascii=False)
                file_handle.write("\n")
            temporary_path.replace(path)
        except OSError as exc:
            raise StorageError(f"Could not write storage file: {path}") from exc
