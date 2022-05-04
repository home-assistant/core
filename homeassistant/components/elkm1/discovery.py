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


def _short_mac(mac_address: str) -> str:
    return mac_address.replace(":", "")[-6:]


@callback
def async_update_entry_from_discovery(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    device: ElkSystem,
) -> bool:
    """Update a config entry from a discovery."""
    if not entry.unique_id or ":" not in entry.unique_id:
        _LOGGER.debug("Adding unique id from discovery: %s", device)
        return hass.config_entries.async_update_entry(
            entry, unique_id=dr.format_mac(device.mac_address)
        )
    _LOGGER.debug("Unique id is already present from discovery: %s", device)
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
        for device in discovered:
            assert isinstance(device, ElkSystem)
            combined_discoveries[device.ip_address] = device

    return list(combined_discoveries.values())


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
                context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                data=asdict(device),
            )
        )
