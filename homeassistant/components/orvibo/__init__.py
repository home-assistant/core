"""The orvibo component."""

from dataclasses import dataclass

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant


@dataclass
class S20Data:
    """S20 data class."""

    CONF_NAME: str
    CONF_HOST: str
    CONF_MAC: str


type S20ConfigEntry = ConfigEntry[S20Data]

PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: core.HomeAssistant, entry: S20ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    entry.runtime_data = S20Data(
        CONF_NAME=entry.data[CONF_NAME],
        CONF_HOST=entry.data[CONF_HOST],
        CONF_MAC=entry.data[CONF_MAC],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: S20ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
