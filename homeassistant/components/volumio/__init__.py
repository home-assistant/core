"""The Volumio integration."""

from dataclasses import dataclass
from typing import Any

from pyvolumio import CannotConnectError, Volumio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

PLATFORMS = [Platform.MEDIA_PLAYER]


@dataclass
class VolumioData:
    """Volumio data class."""

    volumio: Volumio
    info: dict[str, Any]


type VolumioConfigEntry = ConfigEntry[VolumioData]


async def async_setup_entry(hass: HomeAssistant, entry: VolumioConfigEntry) -> bool:
    """Set up Volumio from a config entry."""

    volumio = Volumio(
        entry.data[CONF_HOST], entry.data[CONF_PORT], async_get_clientsession(hass)
    )
    try:
        info = await volumio.get_system_version()
    except CannotConnectError as error:
        raise ConfigEntryNotReady from error

    entry.runtime_data = VolumioData(volumio=volumio, info=info)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VolumioConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
