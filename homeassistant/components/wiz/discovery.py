"""The wiz integration discovery."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import logging

from pywizlight.discovery import DiscoveredBulb, find_wizlights

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_discover_devices(
    hass: HomeAssistant, timeout: int
) -> list[DiscoveredBulb]:
    """Discover wiz devices."""
    broadcast_addrs = await network.async_get_ipv4_broadcast_addresses(hass)
    targets = [str(address) for address in broadcast_addrs]
    combined_discoveries: dict[str, DiscoveredBulb] = {}
    for idx, discovered in enumerate(
        await asyncio.gather(
            *[find_wizlights(timeout, address) for address in targets],
            return_exceptions=True,
        )
    ):
        if isinstance(discovered, Exception):
            _LOGGER.debug("Scanning %s failed with error: %s", targets[idx], discovered)
            continue
        for device in discovered:
            assert isinstance(device, DiscoveredBulb)
            combined_discoveries[device.ip_address] = device

    return list(combined_discoveries.values())


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: list[DiscoveredBulb],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                data=asdict(device),
            )
        )
