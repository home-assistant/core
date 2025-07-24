"""The Lunatone integration."""

from __future__ import annotations

from typing import Final

from lunatone_rest_api_client import Auth, Devices, Info

from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import (
    LunatoneConfigEntry,
    LunatoneData,
    LunatoneDevicesDataUpdateCoordinator,
    LunatoneInfoDataUpdateCoordinator,
)

PLATFORMS: Final[list[Platform]] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: LunatoneConfigEntry) -> bool:
    """Set up Lunatone from a config entry."""

    auth = Auth(async_get_clientsession(hass), entry.data[CONF_URL])
    info = Info(auth)
    devices = Devices(auth)

    coordinator_info = LunatoneInfoDataUpdateCoordinator(hass, entry, info)
    await coordinator_info.async_config_entry_first_refresh()

    coordinator_devices = LunatoneDevicesDataUpdateCoordinator(hass, entry, devices)
    await coordinator_devices.async_config_entry_first_refresh()

    if entry.unique_id is not None:
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title,
            manufacturer="Lunatone",
            sw_version=info.version,
            configuration_url=entry.data[CONF_URL],
        )

    entry.runtime_data = LunatoneData(coordinator_info, coordinator_devices)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LunatoneConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
