"""The Briiv Air Purifier integration."""

from __future__ import annotations

from pybriiv import BriivAPI, BriivError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_HOST, CONF_PORT, CONF_SERIAL_NUMBER, PLATFORMS


class BriivData:
    """Class to store Briiv API data."""

    api: BriivAPI


type BriivConfigEntry = ConfigEntry[BriivData]


async def async_setup_entry(hass: HomeAssistant, entry: BriivConfigEntry) -> bool:
    """Set up Briiv from a config entry."""
    api = BriivAPI(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        serial_number=entry.data[CONF_SERIAL_NUMBER],
    )

    try:
        # Start the UDP listener
        await api.start_listening(hass.loop)
    except BriivError as err:
        await api.stop_listening()
        raise ConfigEntryNotReady from err

    entry.runtime_data = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BriivConfigEntry) -> bool:
    """Unload a config entry."""
    # Access the api from runtime_data
    await entry.runtime_data.api.stop_listening()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
