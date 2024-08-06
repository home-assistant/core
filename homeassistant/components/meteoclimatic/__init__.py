"""Support for Meteoclimatic weather data."""

import logging

from meteoclimatic import MeteoclimaticClient
from meteoclimatic.exceptions import MeteoclimaticError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATION_CODE, DOMAIN, PLATFORMS, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Meteoclimatic entry."""
    station_code = entry.data[CONF_STATION_CODE]
    meteoclimatic_client = MeteoclimaticClient()

    async def async_update_data():
        """Obtain the latest data from Meteoclimatic."""
        try:
            data = await hass.async_add_executor_job(
                meteoclimatic_client.weather_at_station, station_code
            )
        except MeteoclimaticError as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err
        return data.__dict__

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Meteoclimatic weather for {entry.title} ({station_code})",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
