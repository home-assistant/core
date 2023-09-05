"""Support for NWS weather service."""
from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

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
    DOMAIN as WEATHER_DOMAIN,
    CoordinatorWeatherEntity,
    Forecast,
    WeatherEntityFeature,
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow
from homeassistant.util.unit_conversion import SpeedConverter, TemperatureConverter

from . import NWSData, base_unique_id, device_info
from .const import (
    ATTR_FORECAST_DETAILED_DESCRIPTION,
    ATTRIBUTION,
    CONDITION_CLASSES,
    DAYNIGHT,
    DOMAIN,
    FORECAST_VALID_TIME,
    HOURLY,
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
    entity_registry = er.async_get(hass)
    nws_data: NWSData = hass.data[DOMAIN][entry.entry_id]

    entities = [NWSWeather(entry.data, nws_data, DAYNIGHT)]

    # Add hourly entity to legacy config entries
    if entity_registry.async_get_entity_id(
        WEATHER_DOMAIN,
        DOMAIN,
        _calculate_unique_id(entry.data, HOURLY),
    ):
        entities.append(NWSWeather(entry.data, nws_data, HOURLY))

    async_add_entities(entities, False)


if TYPE_CHECKING:

    class NWSForecast(Forecast):
        """Forecast with extra fields needed for NWS."""

        detailed_description: str | None


def _calculate_unique_id(entry_data: MappingProxyType[str, Any], mode: str) -> str:
    """Calculate unique ID."""
    latitude = entry_data[CONF_LATITUDE]
    longitude = entry_data[CONF_LONGITUDE]
    return f"{base_unique_id(latitude, longitude)}_{mode}"


class NWSWeather(CoordinatorWeatherEntity):
    """Representation of a weather condition."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(
        self,
        entry_data: MappingProxyType[str, Any],
        nws_data: NWSData,
        mode: str,
    ) -> None:
        """Initialise the platform with a data instance and station name."""
        super().__init__(
            observation_coordinator=nws_data.coordinator_observation,
            hourly_coordinator=nws_data.coordinator_forecast_hourly,
            twice_daily_coordinator=nws_data.coordinator_forecast,
            hourly_forecast_valid=FORECAST_VALID_TIME,
            twice_daily_forecast_valid=FORECAST_VALID_TIME,
        )
        self.nws = nws_data.api
        self.latitude = entry_data[CONF_LATITUDE]
        self.longitude = entry_data[CONF_LONGITUDE]
        if mode == DAYNIGHT:
            self.coordinator_forecast_legacy = nws_data.coordinator_forecast
        else:
            self.coordinator_forecast_legacy = nws_data.coordinator_forecast_hourly
        self.station = self.nws.station

        self.mode = mode

        self.observation: dict[str, Any] | None = None
        self._forecast_hourly: list[dict[str, Any]] | None = None
        self._forecast_legacy: list[dict[str, Any]] | None = None
        self._forecast_twice_daily: list[dict[str, Any]] | None = None

        self._attr_unique_id = _calculate_unique_id(entry_data, mode)

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator_forecast_legacy.async_add_listener(
                self._handle_legacy_forecast_coordinator_update
            )
        )
        # Load initial data from coordinators
        self._handle_coordinator_update()
        self._handle_hourly_forecast_coordinator_update()
        self._handle_twice_daily_forecast_coordinator_update()
        self._handle_legacy_forecast_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Load data from integration."""
        self.observation = self.nws.observation
        self.async_write_ha_state()

    @callback
    def _handle_hourly_forecast_coordinator_update(self) -> None:
        """Handle updated data from the hourly forecast coordinator."""
        self._forecast_hourly = self.nws.forecast_hourly

    @callback
    def _handle_twice_daily_forecast_coordinator_update(self) -> None:
        """Handle updated data from the twice daily forecast coordinator."""
        self._forecast_twice_daily = self.nws.forecast

    @callback
    def _handle_legacy_forecast_coordinator_update(self) -> None:
        """Handle updated data from the legacy forecast coordinator."""
        if self.mode == DAYNIGHT:
            self._forecast_legacy = self.nws.forecast
        else:
            self._forecast_legacy = self.nws.forecast_hourly
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
            time = cast(str, self.observation.get("iconTime"))

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

    def _forecast(
        self, nws_forecast: list[dict[str, Any]] | None, mode: str
    ) -> list[Forecast] | None:
        """Return forecast."""
        if nws_forecast is None:
            return None
        forecast: list[Forecast] = []
        for forecast_entry in nws_forecast:
            data: NWSForecast = {
                ATTR_FORECAST_DETAILED_DESCRIPTION: forecast_entry.get(
                    "detailedForecast"
                ),
                ATTR_FORECAST_TIME: cast(str, forecast_entry.get("startTime")),
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

            if mode == DAYNIGHT:
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
    def forecast(self) -> list[Forecast] | None:
        """Return forecast."""
        return self._forecast(self._forecast_legacy, self.mode)

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        return self._forecast(self._forecast_hourly, HOURLY)

    @callback
    def _async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the twice daily forecast in native units."""
        return self._forecast(self._forecast_twice_daily, DAYNIGHT)

    @property
    def available(self) -> bool:
        """Return if state is available."""
        last_success = (
            self.coordinator.last_update_success
            and self.coordinator_forecast_legacy.last_update_success
        )
        if (
            self.coordinator.last_update_success_time
            and self.coordinator_forecast_legacy.last_update_success_time
        ):
            last_success_time = (
                utcnow() - self.coordinator.last_update_success_time
                < OBSERVATION_VALID_TIME
                and utcnow() - self.coordinator_forecast_legacy.last_update_success_time
                < FORECAST_VALID_TIME
            )
        else:
            last_success_time = False
        return last_success or last_success_time

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()
        await self.coordinator_forecast_legacy.async_request_refresh()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self.mode == DAYNIGHT

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return device_info(self.latitude, self.longitude)
