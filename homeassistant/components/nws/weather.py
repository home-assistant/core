"""Support for NWS weather service."""
from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_SUNNY,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_IS_DAYTIME,
    ATTR_FORECAST_NATIVE_DEW_POINT,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow
from homeassistant.util.unit_conversion import SpeedConverter, TemperatureConverter
from homeassistant.util.unit_system import UnitSystem

from . import base_unique_id, device_info
from .const import (
    ATTR_FORECAST_DETAILED_DESCRIPTION,
    ATTRIBUTION,
    CONDITION_CLASSES,
    COORDINATOR_FORECAST,
    COORDINATOR_FORECAST_HOURLY,
    COORDINATOR_OBSERVATION,
    DAYNIGHT,
    DOMAIN,
    FORECAST_VALID_TIME,
    HOURLY,
    NWS_DATA,
    OBSERVATION_VALID_TIME,
)

PARALLEL_UPDATES = 0


def convert_condition(time: str, weather: tuple[tuple[str, int | None], ...]) -> str:
    """Convert NWS codes to HA condition.

    Choose first condition in CONDITION_CLASSES that exists in weather code.
    If no match is found, return first condition from NWS
    """
    conditions: list[str] = [w[0] for w in weather]

    # Choose condition with highest priority.
    cond = next(
        (
            key
            for key, value in CONDITION_CLASSES.items()
            if any(condition in value for condition in conditions)
        ),
        conditions[0],
    )

    if cond == "clear":
        if time == "day":
            return ATTR_CONDITION_SUNNY
        if time == "night":
            return ATTR_CONDITION_CLEAR_NIGHT
    return cond


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the NWS weather platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            NWSWeather(entry.data, hass_data, DAYNIGHT, hass.config.units),
            NWSWeather(entry.data, hass_data, HOURLY, hass.config.units),
        ],
        False,
    )


if TYPE_CHECKING:

    class NWSForecast(Forecast):
        """Forecast with extra fields needed for NWS."""

        detailed_description: str | None


class NWSWeather(WeatherEntity):
    """Representation of a weather condition."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(
        self,
        entry_data: MappingProxyType[str, Any],
        hass_data: dict[str, Any],
        mode: str,
        units: UnitSystem,
    ) -> None:
        """Initialise the platform with a data instance and station name."""
        self.nws = hass_data[NWS_DATA]
        self.latitude = entry_data[CONF_LATITUDE]
        self.longitude = entry_data[CONF_LONGITUDE]
        self.coordinator_observation = hass_data[COORDINATOR_OBSERVATION]
        if mode == DAYNIGHT:
            self.coordinator_forecast = hass_data[COORDINATOR_FORECAST]
        else:
            self.coordinator_forecast = hass_data[COORDINATOR_FORECAST_HOURLY]
        self.station = self.nws.station

        self.mode = mode

        self.observation = None
        self._forecast = None

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self.coordinator_observation.async_add_listener(self._update_callback)
        )
        self.async_on_remove(
            self.coordinator_forecast.async_add_listener(self._update_callback)
        )
        self._update_callback()

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self.observation = self.nws.observation
        if self.mode == DAYNIGHT:
            self._forecast = self.nws.forecast
        else:
            self._forecast = self.nws.forecast_hourly

        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the station."""
        return f"{self.station} {self.mode.title()}"

    @property
    def native_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.observation:
            return self.observation.get("temperature")
        return None

    @property
    def native_temperature_unit(self) -> str:
        """Return the current temperature unit."""
        return UnitOfTemperature.CELSIUS

    @property
    def native_pressure(self) -> int | None:
        """Return the current pressure."""
        if self.observation:
            return self.observation.get("seaLevelPressure")
        return None

    @property
    def native_pressure_unit(self) -> str:
        """Return the current pressure unit."""
        return UnitOfPressure.PA

    @property
    def humidity(self) -> float | None:
        """Return the name of the sensor."""
        if self.observation:
            return self.observation.get("relativeHumidity")
        return None

    @property
    def native_wind_speed(self) -> float | None:
        """Return the current windspeed."""
        if self.observation:
            return self.observation.get("windSpeed")
        return None

    @property
    def native_wind_speed_unit(self) -> str:
        """Return the current windspeed."""
        return UnitOfSpeed.KILOMETERS_PER_HOUR

    @property
    def wind_bearing(self) -> int | None:
        """Return the current wind bearing (degrees)."""
        if self.observation:
            return self.observation.get("windDirection")
        return None

    @property
    def condition(self) -> str | None:
        """Return current condition."""
        weather = None
        if self.observation:
            weather = self.observation.get("iconWeather")
            time = self.observation.get("iconTime")

        if weather:
            return convert_condition(time, weather)
        return None

    @property
    def native_visibility(self) -> int | None:
        """Return visibility."""
        if self.observation:
            return self.observation.get("visibility")
        return None

    @property
    def native_visibility_unit(self) -> str:
        """Return visibility unit."""
        return UnitOfLength.METERS

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return forecast."""
        if self._forecast is None:
            return None
        forecast: list[NWSForecast] = []
        for forecast_entry in self._forecast:
            data = {
                ATTR_FORECAST_DETAILED_DESCRIPTION: forecast_entry.get(
                    "detailedForecast"
                ),
                ATTR_FORECAST_TIME: forecast_entry.get("startTime"),
            }

            if (temp := forecast_entry.get("temperature")) is not None:
                data[ATTR_FORECAST_NATIVE_TEMP] = TemperatureConverter.convert(
                    temp, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                )
            else:
                data[ATTR_FORECAST_NATIVE_TEMP] = None

            data[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = forecast_entry.get(
                "probabilityOfPrecipitation"
            )

            if (dewp := forecast_entry.get("dewpoint")) is not None:
                data[ATTR_FORECAST_NATIVE_DEW_POINT] = TemperatureConverter.convert(
                    dewp, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                )
            else:
                data[ATTR_FORECAST_NATIVE_DEW_POINT] = None

            data[ATTR_FORECAST_HUMIDITY] = forecast_entry.get("relativeHumidity")

            if self.mode == DAYNIGHT:
                data[ATTR_FORECAST_IS_DAYTIME] = forecast_entry.get("isDaytime")

            time = forecast_entry.get("iconTime")
            weather = forecast_entry.get("iconWeather")
            data[ATTR_FORECAST_CONDITION] = (
                convert_condition(time, weather) if time and weather else None
            )

            data[ATTR_FORECAST_WIND_BEARING] = forecast_entry.get("windBearing")
            wind_speed = forecast_entry.get("windSpeedAvg")
            if wind_speed is not None:
                data[ATTR_FORECAST_NATIVE_WIND_SPEED] = SpeedConverter.convert(
                    wind_speed,
                    UnitOfSpeed.MILES_PER_HOUR,
                    UnitOfSpeed.KILOMETERS_PER_HOUR,
                )
            else:
                data[ATTR_FORECAST_NATIVE_WIND_SPEED] = None
            forecast.append(data)
        return forecast

    @property
    def unique_id(self) -> str:
        """Return a unique_id for this entity."""
        return f"{base_unique_id(self.latitude, self.longitude)}_{self.mode}"

    @property
    def available(self) -> bool:
        """Return if state is available."""
        last_success = (
            self.coordinator_observation.last_update_success
            and self.coordinator_forecast.last_update_success
        )
        if (
            self.coordinator_observation.last_update_success_time
            and self.coordinator_forecast.last_update_success_time
        ):
            last_success_time = (
                utcnow() - self.coordinator_observation.last_update_success_time
                < OBSERVATION_VALID_TIME
                and utcnow() - self.coordinator_forecast.last_update_success_time
                < FORECAST_VALID_TIME
            )
        else:
            last_success_time = False
        return last_success or last_success_time

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator_observation.async_request_refresh()
        await self.coordinator_forecast.async_request_refresh()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self.mode == DAYNIGHT

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return device_info(self.latitude, self.longitude)
