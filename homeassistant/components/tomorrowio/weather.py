"""Weather component that handles meteorological data for your location."""
from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
import logging
from typing import Any

from pytomorrowio.const import DAILY, FORECASTS, HOURLY, NOWCAST, WeatherCode

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    LENGTH_FEET,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sun import is_up
from homeassistant.util import dt as dt_util
from homeassistant.util.distance import convert as distance_convert
from homeassistant.util.pressure import convert as pressure_convert

from . import TomorrowioDataUpdateCoordinator, TomorrowioEntity
from .const import (
    CLEAR_CONDITIONS,
    CONDITIONS,
    CONF_TIMESTEP,
    DEFAULT_FORECAST_TYPE,
    DOMAIN,
    MAX_FORECASTS,
    TMRW_ATTR_CONDITION,
    TMRW_ATTR_HUMIDITY,
    TMRW_ATTR_OZONE,
    TMRW_ATTR_PRECIPITATION,
    TMRW_ATTR_PRECIPITATION_PROBABILITY,
    TMRW_ATTR_PRESSURE,
    TMRW_ATTR_TEMPERATURE,
    TMRW_ATTR_TEMPERATURE_HIGH,
    TMRW_ATTR_TEMPERATURE_LOW,
    TMRW_ATTR_TIMESTAMP,
    TMRW_ATTR_VISIBILITY,
    TMRW_ATTR_WIND_DIRECTION,
    TMRW_ATTR_WIND_SPEED,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        TomorrowioWeatherEntity(config_entry, coordinator, 4, forecast_type)
        for forecast_type in (DAILY, HOURLY, NOWCAST)
    ]
    async_add_entities(entities)


class BaseTomorrowioWeatherEntity(TomorrowioEntity, WeatherEntity):
    """Base Tomorrow.io weather entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: TomorrowioDataUpdateCoordinator,
        api_version: int,
        forecast_type: str,
    ) -> None:
        """Initialize Tomorrow.io Weather Entity."""
        super().__init__(config_entry, coordinator, api_version)
        self.forecast_type = forecast_type
        self._attr_entity_registry_enabled_default = (
            forecast_type == DEFAULT_FORECAST_TYPE
        )
        self._attr_name = f"{config_entry.data[CONF_NAME]} - {forecast_type.title()}"
        self._attr_unique_id = f"{config_entry.unique_id}_{forecast_type}"

    @staticmethod
    @abstractmethod
    def _translate_condition(
        condition: int | None, sun_is_up: bool = True
    ) -> str | None:
        """Translate Tomorrow.io condition into an HA condition."""

    def _forecast_dict(
        self,
        forecast_dt: datetime,
        use_datetime: bool,
        condition: int,
        precipitation: float | None,
        precipitation_probability: float | None,
        temp: float | None,
        temp_low: float | None,
        wind_direction: float | None,
        wind_speed: float | None,
    ) -> dict[str, Any]:
        """Return formatted Forecast dict from Tomorrow.io forecast data."""
        if use_datetime:
            translated_condition = self._translate_condition(
                condition, is_up(self.hass, forecast_dt)
            )
        else:
            translated_condition = self._translate_condition(condition, True)

        if self.hass.config.units.is_metric:
            if precipitation:
                precipitation = round(
                    distance_convert(precipitation / 12, LENGTH_FEET, LENGTH_METERS)
                    * 1000,
                    4,
                )
            if wind_speed:
                wind_speed = round(
                    distance_convert(wind_speed, LENGTH_MILES, LENGTH_KILOMETERS), 4
                )

        data = {
            ATTR_FORECAST_TIME: forecast_dt.isoformat(),
            ATTR_FORECAST_CONDITION: translated_condition,
            ATTR_FORECAST_PRECIPITATION: precipitation,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: precipitation_probability,
            ATTR_FORECAST_TEMP: temp,
            ATTR_FORECAST_TEMP_LOW: temp_low,
            ATTR_FORECAST_WIND_BEARING: wind_direction,
            ATTR_FORECAST_WIND_SPEED: wind_speed,
        }

        return {k: v for k, v in data.items() if v is not None}

    @property
    @abstractmethod
    def _pressure(self):
        """Return the raw pressure."""

    @property
    def pressure(self):
        """Return the pressure."""
        if self.hass.config.units.is_metric and self._pressure:
            return round(
                pressure_convert(self._pressure, PRESSURE_INHG, PRESSURE_HPA), 4
            )
        return self._pressure

    @property
    @abstractmethod
    def _wind_speed(self):
        """Return the raw wind speed."""

    @property
    def wind_speed(self):
        """Return the wind speed."""
        if self.hass.config.units.is_metric and self._wind_speed:
            return round(
                distance_convert(self._wind_speed, LENGTH_MILES, LENGTH_KILOMETERS), 4
            )
        return self._wind_speed

    @property
    @abstractmethod
    def _visibility(self):
        """Return the raw visibility."""

    @property
    def visibility(self):
        """Return the visibility."""
        if self.hass.config.units.is_metric and self._visibility:
            return round(
                distance_convert(self._visibility, LENGTH_MILES, LENGTH_KILOMETERS), 4
            )
        return self._visibility


class TomorrowioWeatherEntity(BaseTomorrowioWeatherEntity):
    """Entity that talks to Tomorrow.io v4 API to retrieve weather data."""

    _attr_temperature_unit = TEMP_FAHRENHEIT

    @staticmethod
    def _translate_condition(
        condition: int | None, sun_is_up: bool = True
    ) -> str | None:
        """Translate Tomorrow.io condition into an HA condition."""
        if condition is None:
            return None
        # We won't guard here, instead we will fail hard
        condition = WeatherCode(condition)
        if condition in (WeatherCode.CLEAR, WeatherCode.MOSTLY_CLEAR):
            if sun_is_up:
                return CLEAR_CONDITIONS["day"]
            return CLEAR_CONDITIONS["night"]
        return CONDITIONS[condition]

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self._get_current_property(TMRW_ATTR_TEMPERATURE)

    @property
    def _pressure(self):
        """Return the raw pressure."""
        return self._get_current_property(TMRW_ATTR_PRESSURE)

    @property
    def humidity(self):
        """Return the humidity."""
        return self._get_current_property(TMRW_ATTR_HUMIDITY)

    @property
    def _wind_speed(self):
        """Return the raw wind speed."""
        return self._get_current_property(TMRW_ATTR_WIND_SPEED)

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._get_current_property(TMRW_ATTR_WIND_DIRECTION)

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self._get_current_property(TMRW_ATTR_OZONE)

    @property
    def condition(self):
        """Return the condition."""
        return self._translate_condition(
            self._get_current_property(TMRW_ATTR_CONDITION),
            is_up(self.hass),
        )

    @property
    def _visibility(self):
        """Return the raw visibility."""
        return self._get_current_property(TMRW_ATTR_VISIBILITY)

    @property
    def forecast(self):
        """Return the forecast."""
        # Check if forecasts are available
        raw_forecasts = self.coordinator.data.get(FORECASTS, {}).get(self.forecast_type)
        if not raw_forecasts:
            return None

        forecasts = []
        max_forecasts = MAX_FORECASTS[self.forecast_type]
        forecast_count = 0

        # Set default values (in cases where keys don't exist), None will be
        # returned. Override properties per forecast type as needed
        for forecast in raw_forecasts:
            forecast_dt = dt_util.parse_datetime(forecast[TMRW_ATTR_TIMESTAMP])

            # Throw out past data
            if forecast_dt.date() < dt_util.utcnow().date():
                continue

            values = forecast["values"]
            use_datetime = True

            condition = values.get(TMRW_ATTR_CONDITION)
            precipitation = values.get(TMRW_ATTR_PRECIPITATION)
            precipitation_probability = values.get(TMRW_ATTR_PRECIPITATION_PROBABILITY)

            temp = values.get(TMRW_ATTR_TEMPERATURE_HIGH)
            temp_low = values.get(TMRW_ATTR_TEMPERATURE_LOW)
            wind_direction = values.get(TMRW_ATTR_WIND_DIRECTION)
            wind_speed = values.get(TMRW_ATTR_WIND_SPEED)

            if self.forecast_type == DAILY:
                use_datetime = False
                if precipitation:
                    precipitation = precipitation * 24
            elif self.forecast_type == NOWCAST:
                # Precipitation is forecasted in CONF_TIMESTEP increments but in a
                # per hour rate, so value needs to be converted to an amount.
                if precipitation:
                    precipitation = (
                        precipitation / 60 * self._config_entry.options[CONF_TIMESTEP]
                    )

            forecasts.append(
                self._forecast_dict(
                    forecast_dt,
                    use_datetime,
                    condition,
                    precipitation,
                    precipitation_probability,
                    temp,
                    temp_low,
                    wind_direction,
                    wind_speed,
                )
            )

            forecast_count += 1
            if forecast_count == max_forecasts:
                break

        return forecasts
