"""Simple disk cache for provider responses."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


class CacheService:
    """Store JSON payloads on disk with a TTL."""

    def __init__(self, cache_dir: Path, ttl_hours: int = 24) -> None:
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_json(self, key: str) -> Any | None:
        """Return a cached JSON payload if it exists and is fresh."""
        cache_path = self._cache_path(key)
        if not cache_path.exists():
            return None

        try:
            with cache_path.open("r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read cache entry %s: %s", cache_path, exc)
            return None

        expires_at = payload.get("expires_at")
        if not isinstance(expires_at, str):
            return None

        try:
            if datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
                return None
        except ValueError:
            return None

        return payload.get("value")

    def set_json(self, key: str, value: Any) -> None:
        """Store a JSON payload in the cache."""
        cache_path = self._cache_path(key)
        payload = {
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=self.ttl_hours)).isoformat(),
            "value": value,
        }

        try:
            with cache_path.open("w", encoding="utf-8") as file_handle:
                json.dump(payload, file_handle, indent=2, ensure_ascii=False)
                file_handle.write("\n")
        except OSError as exc:
            logger.warning("Could not write cache entry %s: %s", cache_path, exc)

    def _cache_path(self, key: str) -> Path:
        """Return the cache file path for one logical cache key."""
        hashed_key = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{hashed_key}.json"
