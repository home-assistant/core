"""Support for Open-Meteo."""
from __future__ import annotations

from open_meteo import (
    DailyParameters,
    Forecast,
    OpenMeteo,
    OpenMeteoError,
    PrecipitationUnit,
    TemperatureUnit,
    WindSpeedUnit,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_ZONE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Open-Meteo from a config entry."""
    session = async_get_clientsession(hass)
    open_meteo = OpenMeteo(session=session)

    async def async_update_forecast() -> Forecast:
        if (zone := hass.states.get(entry.data[CONF_ZONE])) is None:
            raise UpdateFailed(f"Zone '{entry.data[CONF_ZONE]}' not found")

        try:
            return await open_meteo.forecast(
                latitude=zone.attributes[ATTR_LATITUDE],
                longitude=zone.attributes[ATTR_LONGITUDE],
                current_weather=True,
                daily=[
                    DailyParameters.PRECIPITATION_SUM,
                    DailyParameters.TEMPERATURE_2M_MAX,
                    DailyParameters.TEMPERATURE_2M_MIN,
                    DailyParameters.WEATHER_CODE,
                    DailyParameters.WIND_DIRECTION_10M_DOMINANT,
                    DailyParameters.WIND_SPEED_10M_MAX,
                ],
                precipitation_unit=PrecipitationUnit.MILLIMETERS,
                temperature_unit=TemperatureUnit.CELSIUS,
                timezone="UTC",
                wind_speed_unit=WindSpeedUnit.KILOMETERS_PER_HOUR,
            )
        except OpenMeteoError as err:
            raise UpdateFailed("Open-Meteo API communication error") from err

    coordinator: DataUpdateCoordinator[Forecast] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{entry.data[CONF_ZONE]}",
        update_interval=SCAN_INTERVAL,
        update_method=async_update_forecast,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Open-Meteo config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
