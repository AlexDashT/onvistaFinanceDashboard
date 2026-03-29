"""Centralized logging helpers."""

from __future__ import annotations

import logging

_CONFIGURED = False


def configure_logging() -> None:
    """Configure application logging once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger."""
    configure_logging()
    return logging.getLogger(name)
