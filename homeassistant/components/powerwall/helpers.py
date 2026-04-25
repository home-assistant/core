"""Helpers for the powerwall integration."""

from __future__ import annotations

from tesla_powerwall import ApiError

# tesla_powerwall 0.5.2 raises ApiError with a fixed message of the form
# "Powerwall api error: The url <url> returned error 404". The library does
# not expose the underlying HTTP status code, so we match the exact phrase
# produced at tesla_powerwall/api.py:_handle_error. Once upstream exposes a
# status_code attribute on ApiError this becomes a one-line attribute check.
_API_404_MARKER = "returned error 404"


def is_api_404(err: ApiError) -> bool:
    """Return True if an ApiError represents an HTTP 404 from the gateway."""
    return _API_404_MARKER in str(err)
