"""Support for IPMA weather service."""
from __future__ import annotations

import logging

import async_timeout
from pyipma.api import IPMA_API
from pyipma.forecast import Forecast
from pyipma.location import Location

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_MODE,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sun import is_up
from homeassistant.util import Throttle

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DATA_API,
    DATA_LOCATION,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)
from .entity import IPMADevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    api = hass.data[DOMAIN][config_entry.entry_id][DATA_API]
    location = hass.data[DOMAIN][config_entry.entry_id][DATA_LOCATION]
    mode = config_entry.data[CONF_MODE]

    # Migrate old unique_id
    @callback
    def _async_migrator(entity_entry: er.RegistryEntry):
        # Reject if new unique_id
        if entity_entry.unique_id.count(",") == 2:
            return None

        new_unique_id = (
            f"{location.station_latitude}, {location.station_longitude}, {mode}"
        )

        _LOGGER.info(
            "Migrating unique_id from [%s] to [%s]",
            entity_entry.unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await er.async_migrate_entries(hass, config_entry.entry_id, _async_migrator)

    async_add_entities([IPMAWeather(location, api, config_entry)], True)


class IPMAWeather(WeatherEntity, IPMADevice):
    """Representation of a weather condition."""

    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_attribution = ATTRIBUTION
    _attr_name = None

    def __init__(self, api: IPMA_API, location: Location, entry: ConfigEntry) -> None:
        """Initialise the platform with a data instance and station name."""
        IPMADevice.__init__(self, api, location, entry)
        self._api = api
        self._mode = entry.data.get(CONF_MODE)
        self._period = 1 if entry.data.get(CONF_MODE) == "hourly" else 24
        self._observation = None
        self._forecast: list[Forecast] = []
        self._attr_unique_id = f"{self._location.station_latitude}, {self._location.station_longitude}, {self._mode}"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update Condition and Forecast."""
        async with async_timeout.timeout(10):
            new_observation = await self._location.observation(self._api)
            new_forecast = await self._location.forecast(self._api, self._period)

            if new_observation:
                self._observation = new_observation
            else:
                _LOGGER.warning("Could not update weather observation")

            if new_forecast:
                self._forecast = new_forecast
            else:
                _LOGGER.warning("Could not update weather forecast")

            _LOGGER.debug(
                "Updated location %s based on %s, current observation %s",
                self._location.name,
                self._location.station,
                self._observation,
            )

    def _condition_conversion(self, identifier, forecast_dt):
        """Convert from IPMA weather_type id to HA."""
        if identifier == 1 and not is_up(self.hass, forecast_dt):
            identifier = -identifier

        return next(
            (k for k, v in CONDITION_CLASSES.items() if identifier in v),
            None,
        )

    @property
    def condition(self):
        """Return the current condition."""
        if not self._forecast:
            return

        return self._condition_conversion(self._forecast[0].weather_type.id, None)

    @property
    def native_temperature(self):
        """Return the current temperature."""
        if not self._observation:
            return None

        return self._observation.temperature

    @property
    def native_pressure(self):
        """Return the current pressure."""
        if not self._observation:
            return None

        return self._observation.pressure

    @property
    def humidity(self):
        """Return the name of the sensor."""
        if not self._observation:
            return None

        return self._observation.humidity

    @property
    def native_wind_speed(self):
        """Return the current windspeed."""
        if not self._observation:
            return None

        return self._observation.wind_intensity_km

    @property
    def wind_bearing(self):
        """Return the current wind bearing (degrees)."""
        if not self._observation:
            return None

        return self._observation.wind_direction

    @property
    def forecast(self):
        """Return the forecast array."""
        if not self._forecast:
            return []

        return [
            {
                ATTR_FORECAST_TIME: data_in.forecast_date,
                ATTR_FORECAST_CONDITION: self._condition_conversion(
                    data_in.weather_type.id, data_in.forecast_date
                ),
                ATTR_FORECAST_NATIVE_TEMP_LOW: data_in.min_temperature,
                ATTR_FORECAST_NATIVE_TEMP: data_in.max_temperature,
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: data_in.precipitation_probability,
                ATTR_FORECAST_NATIVE_WIND_SPEED: data_in.wind_strength,
                ATTR_FORECAST_WIND_BEARING: data_in.wind_direction,
            }
            for data_in in self._forecast
        ]
