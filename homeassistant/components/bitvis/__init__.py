"""The Bitvis Power Hub integration."""

import logging

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import BitvisConfigEntry, BitvisDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BitvisConfigEntry) -> bool:
    """Set up Bitvis Power Hub from a config entry."""
    coordinator = BitvisDataUpdateCoordinator(
        hass, entry, entry.data[CONF_HOST], entry.data[CONF_PORT]
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BitvisConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        await entry.runtime_data.async_stop()
    return unload_ok
