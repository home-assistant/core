"""The Zinvolt integration."""

from __future__ import annotations

import asyncio

from zinvolt import ZinvoltClient
from zinvolt.exceptions import ZinvoltError

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import ZinvoltConfigEntry, ZinvoltDeviceCoordinator

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ZinvoltConfigEntry) -> bool:
    """Set up Zinvolt from a config entry."""
    session = async_get_clientsession(hass)
    client = ZinvoltClient(entry.data[CONF_ACCESS_TOKEN], session=session)

    try:
        batteries = await client.get_batteries()
    except ZinvoltError as err:
        raise ConfigEntryNotReady from err

    coordinators: dict[str, ZinvoltDeviceCoordinator] = {}
    tasks = []
    for battery in batteries:
        coordinator = ZinvoltDeviceCoordinator(hass, entry, client, battery)
        tasks.append(coordinator.async_config_entry_first_refresh())
        coordinators[battery.identifier] = coordinator
    await asyncio.gather(*tasks)

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZinvoltConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
