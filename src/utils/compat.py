"""Compatibility helpers for Python features that vary by version."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import timezone
from enum import Enum
from itertools import islice
from typing import TypeVar

try:
    from datetime import UTC as UTC
except ImportError:
    UTC = timezone.utc

try:
    from enum import StrEnum as StrEnum
except ImportError:
    class StrEnum(str, Enum):
        """Fallback for Python versions older than 3.11."""


T = TypeVar("T")


def batched(iterable: Iterable[T], size: int) -> Iterator[tuple[T, ...]]:
    """Yield fixed-size batches compatible with Python versions before 3.12."""
    if size < 1:
        raise ValueError("Batch size must be at least 1.")

    iterator = iter(iterable)
    while batch := tuple(islice(iterator, size)):
        yield batch
