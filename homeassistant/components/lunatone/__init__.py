"""The Lunatone integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from lunatone_dali_api_client import Auth, Devices, Info

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


@dataclass
class LunatoneDALIIoTData:
    """Lunatone DALI IoT data class."""

    coordinator_info: DataUpdateCoordinator
    info: Info

    coordinator_devices: DataUpdateCoordinator
    devices: Devices


type LunatoneDALIIoTConfigEntry = ConfigEntry[LunatoneDALIIoTData]


async def async_setup_entry(
    hass: HomeAssistant, entry: LunatoneDALIIoTConfigEntry
) -> bool:
    """Set up Lunatone from a config entry."""

    entry.async_on_unload(entry.add_update_listener(update_listener))

    auth = Auth(async_get_clientsession(hass), entry.data[CONF_URL])
    info = Info(auth)
    devices = Devices(auth)

    coordinator_info = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN + "-info",
        update_method=info.async_update,
    )
    await coordinator_info.async_config_entry_first_refresh()
    coordinator_devices = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN + "-devices",
        update_method=devices.async_update,
    )
    await coordinator_devices.async_config_entry_first_refresh()

    entry.runtime_data = LunatoneDALIIoTData(
        coordinator_info, info, coordinator_devices, devices
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LunatoneDALIIoTConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
