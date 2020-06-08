"""Support for Meteo-France weather data."""
import asyncio
from datetime import timedelta
import logging

from meteofrance.client import MeteoFranceClient
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CITY,
    COORDINATOR_ALERT,
    COORDINATOR_FORECAST,
    COORDINATOR_RAIN,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


CITY_SCHEMA = vol.Schema({vol.Required(CONF_CITY): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [CITY_SCHEMA]))}, extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up Meteo-France from legacy config file."""
    conf = config.get(DOMAIN)
    if not conf:
        return True

    for city_conf in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=city_conf
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up an Meteo-France account from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]

    # coordinator = MeteoFranceDataUpdateCoordinator(hass, latitude, longitude)

    client = MeteoFranceClient()

    async def _async_update_data_forecast_forecast():
        """Fetch data from API endpoint."""
        return await hass.async_add_job(client.get_forecast, latitude, longitude)

    async def _async_update_data_rain():
        """Fetch data from API endpoint."""
        return await hass.async_add_job(client.get_rain, latitude, longitude)

    async def _async_update_data_alert():
        """Fetch data from API endpoint."""
        return await hass.async_add_job(
            client.get_warning_current_phenomenoms, department
        )

    coordinator_forecast = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Météo-France forecast for city {entry.title}",
        update_method=_async_update_data_forecast_forecast,
        update_interval=SCAN_INTERVAL,
    )

    coordinator_rain = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Météo-France rain for city {entry.title}",
        update_method=_async_update_data_rain,
        update_interval=SCAN_INTERVAL,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator_forecast.async_refresh()
    await coordinator_rain.async_refresh()

    if (
        not coordinator_forecast.last_update_success
        or not coordinator_rain.last_update_success
    ):
        raise ConfigEntryNotReady

    department = coordinator_forecast.data.position["dept"]
    if department:
        coordinator_alert = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"Météo-France alert for department {department}",
            update_method=_async_update_data_alert,
            update_interval=SCAN_INTERVAL,
        )

        await coordinator_alert.async_refresh()

        if not coordinator_alert.last_update_success:
            raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR_FORECAST: coordinator_forecast,
        COORDINATOR_RAIN: coordinator_rain,
        COORDINATOR_ALERT: coordinator_alert,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# class MeteoFranceDataUpdateCoordinator(DataUpdateCoordinator):
#     """Define an object to hold Meteo-France data."""

#     def __init__(self, hass, latitude, longitude):
#         """Initialize."""
#         self.latitude = latitude
#         self.longitude = longitude

#         auth = AuthMeteofrance()
#         self.client = MeteofranceClient(auth)

#         super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

#     async def _async_update_data(self):
#         """Update data via library."""
#         with async_timeout.timeout(20):
#             try:
#                 return await self.hass.async_add_executor_job(
#                     self.client.get_forecast, self.latitude, self.longitude
#                 )
#             except Exception as exp:  # pylint: disable=broad-except
#                 raise UpdateFailed(exp)
