"""Base provider exceptions and shared interfaces."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base exception raised by provider modules."""


class ProviderNetworkError(ProviderError):
    """Raised when a provider request fails due to network issues."""


class ProviderParsingError(ProviderError):
    """Raised when a provider response cannot be parsed reliably."""


class InstrumentNotFoundError(ProviderError):
    """Raised when no matching instrument can be found."""


class ChartDataUnavailableError(ProviderError):
    """Raised when a chart series cannot be loaded for an instrument."""
