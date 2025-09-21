"""Common functions for SSDP discovery."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address

from homeassistant.components import network
from homeassistant.core import HomeAssistant


async def async_build_source_set(hass: HomeAssistant) -> set[IPv4Address | IPv6Address]:
    """Build the list of ssdp sources."""
    return {
        source_ip
        for source_ip in await network.async_get_enabled_source_ips(hass)
        if not source_ip.is_loopback
        and not source_ip.is_global
        and ((source_ip.version == 6 and source_ip.scope_id) or source_ip.version == 4)
    }
