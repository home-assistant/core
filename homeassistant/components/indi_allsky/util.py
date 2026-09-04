"""Utilities for the INDI Allsky integration."""

import ipaddress
import ssl

from homeassistant.util.ssl import get_default_context, get_default_no_verify_context


def normalize_host(host: str) -> str:
    """Normalize hostname or IP address into canonical form."""
    host_clean = host.strip(" []")
    try:
        return str(ipaddress.ip_address(host_clean))
    except ValueError:
        return host_clean


def get_ssl_context(ssl_enabled: bool, verify_ssl: bool) -> bool | ssl.SSLContext:
    """Return SSL configuration for IndiAllSkyClient."""
    if not ssl_enabled:
        return False
    if not verify_ssl:
        return get_default_no_verify_context()
    return get_default_context()
