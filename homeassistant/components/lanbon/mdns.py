"""Zeroconf properties to LOIP discovery. Token is never read."""

from typing import Any

from aiolanbon.discovery import discovered_from_mdns, parse_mdns_txt
from aiolanbon.models import DiscoveredGateway

from .const import DEFAULT_PORT


def gateway_from_zeroconf(
    host: str,
    port: int | None,
    properties: dict[Any, Any] | None,
) -> DiscoveredGateway:
    """Build discovery info from Zeroconf, ignoring secret TXT keys."""
    return discovered_from_mdns(host, port or DEFAULT_PORT, properties or {})


def txt_without_secrets(properties: dict[Any, Any] | None) -> dict[str, str]:
    """Return allowed mDNS TXT fields with secrets stripped."""
    return parse_mdns_txt(properties)
