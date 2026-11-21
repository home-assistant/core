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
        return host_clean.lower().removesuffix(".")


def is_ip_address(host: str) -> bool:
    """Return True if host is an IP address."""
    try:
        ipaddress.ip_address(host.strip(" []"))
    except ValueError:
        return False
    else:
        return True


def get_ssl_context(ssl_enabled: bool, verify_ssl: bool) -> bool | ssl.SSLContext:
    """Return SSL configuration for IndiAllSkyClient."""
    if not ssl_enabled:
        return False
    if not verify_ssl:
        return get_default_no_verify_context()
    return get_default_context()
