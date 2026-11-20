"""Helpers for the powerwall integration."""

from tesla_powerwall import ApiError

# tesla_powerwall 0.5.2 raises ApiError with a message that embeds the HTTP
# status but not a structured status code, e.g. "... returned error 404". The
# exact prefix varies by call site (the request method and url are interpolated
# in), but the "returned error <status>" suffix is stable, so we match that
# phrase. Once upstream exposes a status_code attribute on ApiError this becomes
# a one-line attribute check.
_API_404_MARKER = "returned error 404"


def is_api_404(err: ApiError) -> bool:
    """Return True if an ApiError represents an HTTP 404 from the gateway."""
    return _API_404_MARKER in str(err)
