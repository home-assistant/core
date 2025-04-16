"""Tests for the dhcp integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast
from unittest.mock import patch

import aiodhcpwatcher

from homeassistant.components import dhcp
from homeassistant.components.dhcp.models import DHCPData
from homeassistant.core import HomeAssistant


async def async_get_handle_dhcp_packet(
    hass: HomeAssistant,
    integration_matchers: dhcp.DhcpMatchers,
    address_data: dict | None = None,
) -> Callable[[Any], Awaitable[None]]:
    """Make a handler for a dhcp packet."""
    if address_data is None:
        address_data = {}
    dhcp_watcher = dhcp.DHCPWatcher(
        hass,
        DHCPData(integration_matchers, set(), address_data),
    )
    with patch("aiodhcpwatcher.async_start"):
        await dhcp_watcher.async_start()

    def _async_handle_dhcp_request(request: aiodhcpwatcher.DHCPRequest) -> None:
        dhcp_watcher._async_process_dhcp_request(request)

    handler = aiodhcpwatcher.make_packet_handler(_async_handle_dhcp_request)

    async def _async_handle_dhcp_packet(packet):
        handler(packet)

    return cast("Callable[[Any], Awaitable[None]]", _async_handle_dhcp_packet)
