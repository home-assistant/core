"""Utility helpers for the Teltonika integration."""

from __future__ import annotations

from yarl import URL


def normalize_url(host: str) -> str:
    """Normalize host input to a base URL without path.

    Returns just the scheme://host part, without /api.
    Ensures the URL has a scheme (defaults to HTTPS).
    """
    host_input = host.strip().rstrip("/")

    # Parse or construct URL
    if host_input.startswith(("http://", "https://")):
        url = URL(host_input)
    else:
        # handle as scheme-relative URL and add HTTPS scheme by default
        url = URL(f"//{host_input}").with_scheme("https")

    # Return base URL without path, only including scheme, host and port
    return str(url.origin())


def get_url_variants(host: str) -> list[str]:
    """Get URL variants to try during setup (HTTPS first, then HTTP fallback)."""
    normalized = normalize_url(host)
    url = URL(normalized)

    # If user specified a scheme, only try that
    if host.strip().startswith(("http://", "https://")):
        return [normalized]

    # Otherwise try HTTPS first, then HTTP
    https_url = str(url.with_scheme("https"))
    http_url = str(url.with_scheme("http"))
    return [https_url, http_url]
