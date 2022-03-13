"""The zamg component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATION_ID, DOMAIN, LOGGER, MIN_TIME_BETWEEN_UPDATES
from .sensor import ZamgData

PLATFORMS = (Platform.WEATHER, Platform.SENSOR)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zamg from config entry."""
    station_id = entry.data[CONF_STATION_ID]
    zamg_client = ZamgData(station_id)

    async def async_update_data():
        """Obtain data from zamg."""
        try:
            await hass.async_add_executor_job(zamg_client.update)
            return zamg_client.data
        except (ValueError, TypeError) as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"ZAMG weather for {entry.title} ({station_id})",
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Set up all platforms for this device/entry.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ZAMG config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
