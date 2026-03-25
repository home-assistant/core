"""The Meteo.lt integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import CONF_PLACE_CODE, PLATFORMS
from .coordinator import MeteoLtConfigEntry, MeteoLtUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: MeteoLtConfigEntry) -> bool:
    """Set up Meteo.lt from a config entry."""

    coordinator = MeteoLtUpdateCoordinator(hass, entry.data[CONF_PLACE_CODE], entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeteoLtConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
