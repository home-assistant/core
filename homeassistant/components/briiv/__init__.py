"""The Briiv Air Purifier integration."""

from __future__ import annotations

from dataclasses import dataclass

from pybriiv import BriivAPI, BriivError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SERIAL_NUMBER, PLATFORMS


@dataclass
class BriivData:
    """Class to store Briiv API data."""

    api: BriivAPI


# Type alias for the config entry
BriivConfigEntry = ConfigEntry[BriivData]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Briiv from a config entry."""
    api = BriivAPI(
        host=entry.data["host"],
        port=entry.data["port"],
        serial_number=entry.data[CONF_SERIAL_NUMBER],
    )

    try:
        # Start the UDP listener
        await api.start_listening(hass.loop)
    except BriivError as err:
        await api.stop_listening()
        raise ConfigEntryNotReady from err

    # Store the API in runtime_data instead of hass.data
    entry.runtime_data = BriivData(api=api)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Access the api from runtime_data
    api: BriivAPI = entry.runtime_data.api
    await api.stop_listening()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
