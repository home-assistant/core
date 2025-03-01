"""The duotecno integration."""

from __future__ import annotations

from duotecno.controller import PyDuotecno
from duotecno.exceptions import InvalidPassword, LoadFailure

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SWITCH,
]


type DuotecnoConfigEntry = ConfigEntry[PyDuotecno]


async def async_setup_entry(hass: HomeAssistant, entry: DuotecnoConfigEntry) -> bool:
    """Set up duotecno from a config entry."""

    controller = PyDuotecno()
    try:
        await controller.connect(
            entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_PASSWORD]
        )
    except (OSError, InvalidPassword, LoadFailure) as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DuotecnoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
