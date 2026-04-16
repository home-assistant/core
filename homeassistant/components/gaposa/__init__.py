"""The Gaposa integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import UPDATE_INTERVAL
from .coordinator import DataUpdateCoordinatorGaposa

PLATFORMS: list[Platform] = [Platform.COVER]

type GaposaConfigEntry = ConfigEntry[DataUpdateCoordinatorGaposa]


async def async_setup_entry(hass: HomeAssistant, entry: GaposaConfigEntry) -> bool:
    """Set up Gaposa from a config entry."""
    coordinator = DataUpdateCoordinatorGaposa(
        hass,
        entry,
        api_key=entry.data[CONF_API_KEY],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        name=entry.title,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GaposaConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
    return unload_ok
