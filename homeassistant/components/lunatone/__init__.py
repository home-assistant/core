"""The Lunatone integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from lunatone_dali_api_client import Auth, Devices

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


@dataclass
class LunatoneDALIIoTData:
    """Lunatone DALI IoT data class."""

    coordinator: DataUpdateCoordinator
    devices: Devices


type LunatoneDALIIoTConfigEntry = ConfigEntry[LunatoneDALIIoTData]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lunatone from a config entry."""

    auth = Auth(async_get_clientsession(hass), entry.data[CONF_URL])
    devices = Devices(auth)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Lunatone",
        update_method=devices.async_update,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = LunatoneDALIIoTData(coordinator, devices)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
