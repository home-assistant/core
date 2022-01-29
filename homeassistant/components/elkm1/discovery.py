"""The elkm1 integration discovery."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import logging

from elkm1_lib.discovery import AIOELKDiscovery, ElkSystem

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DISCOVER_SCAN_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def async_update_entry_from_discovery(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    device: ElkSystem,
) -> bool:
    """Update a config entry from a discovery."""
    if not entry.unique_id or ":" not in entry.unique_id:
        return hass.config_entries.async_update_entry(
            entry, unique_id=dr.format_mac(device.mac_address)
        )
    return False


async def async_discover_devices(
    hass: HomeAssistant, timeout: int, address: str | None = None
) -> list[ElkSystem]:
    """Discover elkm1 devices."""
    if address:
        targets = [address]
    else:
        targets = [
            str(address)
            for address in await network.async_get_ipv4_broadcast_addresses(hass)
        ]

    scanner = AIOELKDiscovery()
    combined_discoveries: dict[str, ElkSystem] = {}
    for idx, discovered in enumerate(
        await asyncio.gather(
            *[
                scanner.async_scan(timeout=timeout, address=address)
                for address in targets
            ],
            return_exceptions=True,
        )
    ):
        if isinstance(discovered, Exception):
            _LOGGER.debug("Scanning %s failed with error: %s", targets[idx], discovered)
            continue
        assert isinstance(discovered, ElkSystem)
        for device in discovered:
            combined_discoveries[device.ip_address] = device

    if not address:
        return list(combined_discoveries.values())

    if address in combined_discoveries:
        return [combined_discoveries[address]]

    return []


async def async_discover_device(hass: HomeAssistant, host: str) -> ElkSystem | None:
    """Direct discovery at a single ip instead of broadcast."""
    # If we are missing the unique_id we should be able to fetch it
    # from the device by doing a directed discovery at the host only
    for device in await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT, host):
        if device.ip_address == host:
            return device
    return None


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: list[ElkSystem],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_DISCOVERY},
                data=asdict(device),
            )
        )
