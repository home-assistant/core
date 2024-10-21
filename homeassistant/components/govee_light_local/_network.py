"""Custom private network functions for Govee light local."""

from __future__ import annotations

from ipaddress import IPv4Address

from homeassistant.components import network
from homeassistant.core import HomeAssistant


async def _async_get_all_source_ipv4_ips(
    hass: HomeAssistant,
) -> list[IPv4Address]:
    """Build the list of all source v4 ips."""

    adapters = await network.async_get_adapters(hass)

    sources: list[IPv4Address] = []
    for adapter in adapters:
        if adapter["ipv4"]:
            addrs_ipv4 = [IPv4Address(ipv4["address"]) for ipv4 in adapter["ipv4"]]
            sources.extend(addrs_ipv4)
        if adapter["ipv6"]:
            continue

    return sources
