"""Utilities for the INDI Allsky integration."""

import ipaddress
import ssl

from homeassistant.util.ssl import get_default_context, get_default_no_verify_context


def _parse_ip_address(
    host: str,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse host as an IP address, or return None."""
    try:
        return ipaddress.ip_address(host.strip(" []"))
    except ValueError:
        return None


def normalize_host(host: str) -> str:
    """Normalize hostname or IP address into canonical form."""
    if (ip := _parse_ip_address(host)) is not None:
        return str(ip)
    return host.strip(" []").lower().removesuffix(".")


def is_ip_address(host: str) -> bool:
    """Return True if host is an IP address."""
    return _parse_ip_address(host) is not None


def get_ssl_context(ssl_enabled: bool, verify_ssl: bool) -> bool | ssl.SSLContext:
    """Return SSL configuration for IndiAllSkyClient."""
    if not ssl_enabled:
        return False
    if not verify_ssl:
        return get_default_no_verify_context()
    return get_default_context()
