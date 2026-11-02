"""Utility helpers for the Teltonika integration."""

from collections.abc import Mapping
from typing import Any

from yarl import URL

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL


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


def url_to_entry_data(url: str) -> dict[str, Any]:
    """Split a base URL into the host, port and SSL config entry data."""
    parsed = URL(normalize_url(url))
    return {
        CONF_HOST: parsed.host,
        CONF_PORT: parsed.port,
        CONF_SSL: parsed.scheme == "https",
    }


def entry_data_to_url(data: Mapping[str, Any]) -> str:
    """Build the base URL from the host, port and SSL config entry data."""
    return str(
        URL.build(
            scheme="https" if data[CONF_SSL] else "http",
            host=data[CONF_HOST],
            port=data[CONF_PORT],
        )
    )
