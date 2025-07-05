"""DataUpdateCoordinator for the Open-Meteo integration."""

from __future__ import annotations

import asyncio
from typing import Any, NamedTuple

from open_meteo import (
    AirQuality,
    AirQualityParameters,
    DailyParameters,
    Forecast,
    HourlyParameters,
    OpenMeteo,
    OpenMeteoError,
    PrecipitationUnit,
    TemperatureUnit,
    WindSpeedUnit,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type OpenMeteoConfigEntry = ConfigEntry[OpenMeteoDataUpdateCoordinator]


class OpenMeteoData(NamedTuple):
    """A named tuple representing open meteo data."""

    forecast: Forecast
    air_quality: AirQuality

    def to_dict(self) -> dict[str, Any]:
        """Return a dict representation of this data."""
        return {k: v.to_dict() for k, v in self._asdict().items()}


class OpenMeteoDataUpdateCoordinator(DataUpdateCoordinator[OpenMeteoData]):
    """A Open-Meteo Data Update Coordinator."""

    config_entry: OpenMeteoConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: OpenMeteoConfigEntry) -> None:
        """Initialize the Open-Meteo coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.data[CONF_ZONE]}",
            update_interval=SCAN_INTERVAL,
        )
        session = async_get_clientsession(hass)
        self.open_meteo = OpenMeteo(session=session)

    async def _async_update_data(self) -> OpenMeteoData:
        """Fetch data from Sensibo."""
        if (zone := self.hass.states.get(self.config_entry.data[CONF_ZONE])) is None:
            raise UpdateFailed(f"Zone '{self.config_entry.data[CONF_ZONE]}' not found")

        try:
            return OpenMeteoData(
                *await asyncio.gather(
                    self.open_meteo.forecast(
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
                        hourly=[
                            HourlyParameters.PRECIPITATION,
                            HourlyParameters.TEMPERATURE_2M,
                            HourlyParameters.WEATHER_CODE,
                        ],
                        precipitation_unit=PrecipitationUnit.MILLIMETERS,
                        temperature_unit=TemperatureUnit.CELSIUS,
                        timezone="UTC",
                        wind_speed_unit=WindSpeedUnit.KILOMETERS_PER_HOUR,
                    ),
                    self.open_meteo.air_quality(
                        latitude=zone.attributes[ATTR_LATITUDE],
                        longitude=zone.attributes[ATTR_LONGITUDE],
                        timezone="UTC",
                        current=[
                            AirQualityParameters.OZONE,
                            AirQualityParameters.UV_INDEX,
                        ],
                    ),
                )
            )
        except OpenMeteoError as err:
            raise UpdateFailed("Open-Meteo API communication error") from err
