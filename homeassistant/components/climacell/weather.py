"""Weather component that handles meteorological data for your location."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Any

from pyclimacell.const import (
    CURRENT,
    DAILY,
    FORECASTS,
    HOURLY,
    NOWCAST,
    PrecipitationType,
    WeatherCode,
)

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
    CONF_API_VERSION,
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

from . import ClimaCellDataUpdateCoordinator, ClimaCellEntity
from .const import (
    ATTR_CLOUD_COVER,
    ATTR_PRECIPITATION_TYPE,
    ATTR_WIND_GUST,
    CC_ATTR_CLOUD_COVER,
    CC_ATTR_CONDITION,
    CC_ATTR_HUMIDITY,
    CC_ATTR_OZONE,
    CC_ATTR_PRECIPITATION,
    CC_ATTR_PRECIPITATION_PROBABILITY,
    CC_ATTR_PRECIPITATION_TYPE,
    CC_ATTR_PRESSURE,
    CC_ATTR_TEMPERATURE,
    CC_ATTR_TEMPERATURE_HIGH,
    CC_ATTR_TEMPERATURE_LOW,
    CC_ATTR_TIMESTAMP,
    CC_ATTR_VISIBILITY,
    CC_ATTR_WIND_DIRECTION,
    CC_ATTR_WIND_GUST,
    CC_ATTR_WIND_SPEED,
    CC_V3_ATTR_CLOUD_COVER,
    CC_V3_ATTR_CONDITION,
    CC_V3_ATTR_HUMIDITY,
    CC_V3_ATTR_OZONE,
    CC_V3_ATTR_PRECIPITATION,
    CC_V3_ATTR_PRECIPITATION_DAILY,
    CC_V3_ATTR_PRECIPITATION_PROBABILITY,
    CC_V3_ATTR_PRECIPITATION_TYPE,
    CC_V3_ATTR_PRESSURE,
    CC_V3_ATTR_TEMPERATURE,
    CC_V3_ATTR_TEMPERATURE_HIGH,
    CC_V3_ATTR_TEMPERATURE_LOW,
    CC_V3_ATTR_TIMESTAMP,
    CC_V3_ATTR_VISIBILITY,
    CC_V3_ATTR_WIND_DIRECTION,
    CC_V3_ATTR_WIND_GUST,
    CC_V3_ATTR_WIND_SPEED,
    CLEAR_CONDITIONS,
    CONDITIONS,
    CONDITIONS_V3,
    CONF_TIMESTEP,
    DEFAULT_FORECAST_TYPE,
    DOMAIN,
    MAX_FORECASTS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    api_version = config_entry.data[CONF_API_VERSION]

    api_class = ClimaCellV3WeatherEntity if api_version == 3 else ClimaCellWeatherEntity
    entities = [
        api_class(config_entry, coordinator, api_version, forecast_type)
        for forecast_type in (DAILY, HOURLY, NOWCAST)
    ]
    async_add_entities(entities)


class BaseClimaCellWeatherEntity(ClimaCellEntity, WeatherEntity):
    """Base ClimaCell weather entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: ClimaCellDataUpdateCoordinator,
        api_version: int,
        forecast_type: str,
    ) -> None:
        """Initialize ClimaCell Weather Entity."""
        super().__init__(config_entry, coordinator, api_version)
        self.forecast_type = forecast_type

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        if self.forecast_type == DEFAULT_FORECAST_TYPE:
            return True

        return False

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._config_entry.data[CONF_NAME]} - {self.forecast_type.title()}"

    @property
    def unique_id(self) -> str:
        """Return the unique id of the entity."""
        return f"{self._config_entry.unique_id}_{self.forecast_type}"

    @staticmethod
    @abstractmethod
    def _translate_condition(
        condition: int | None, sun_is_up: bool = True
    ) -> str | None:
        """Translate ClimaCell condition into an HA condition."""

    def _forecast_dict(
        self,
        forecast_dt: datetime,
        use_datetime: bool,
        condition: str,
        precipitation: float | None,
        precipitation_probability: float | None,
        temp: float | None,
        temp_low: float | None,
        wind_direction: float | None,
        wind_speed: float | None,
    ) -> dict[str, Any]:
        """Return formatted Forecast dict from ClimaCell forecast data."""
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
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional state attributes."""
        wind_gust = self.wind_gust
        if wind_gust and self.hass.config.units.is_metric:
            wind_gust = round(
                distance_convert(self.wind_gust, LENGTH_MILES, LENGTH_KILOMETERS), 4
            )
        cloud_cover = self.cloud_cover
        return {
            ATTR_CLOUD_COVER: cloud_cover,
            ATTR_WIND_GUST: wind_gust,
            ATTR_PRECIPITATION_TYPE: self.precipitation_type,
        }

    @property
    @abstractmethod
    def cloud_cover(self):
        """Return cloud cover."""

    @property
    @abstractmethod
    def wind_gust(self):
        """Return wind gust speed."""

    @property
    @abstractmethod
    def precipitation_type(self):
        """Return precipitation type."""

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


class ClimaCellWeatherEntity(BaseClimaCellWeatherEntity):
    """Entity that talks to ClimaCell v4 API to retrieve weather data."""

    @staticmethod
    def _translate_condition(
        condition: int | None, sun_is_up: bool = True
    ) -> str | None:
        """Translate ClimaCell condition into an HA condition."""
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
        return self._get_current_property(CC_ATTR_TEMPERATURE)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def _pressure(self):
        """Return the raw pressure."""
        return self._get_current_property(CC_ATTR_PRESSURE)

    @property
    def humidity(self):
        """Return the humidity."""
        return self._get_current_property(CC_ATTR_HUMIDITY)

    @property
    def wind_gust(self):
        """Return the wind gust speed."""
        return self._get_current_property(CC_ATTR_WIND_GUST)

    @property
    def cloud_cover(self):
        """Reteurn the cloud cover."""
        return self._get_current_property(CC_ATTR_CLOUD_COVER)

    @property
    def precipitation_type(self):
        """Return precipitation type."""
        precipitation_type = self._get_current_property(CC_ATTR_PRECIPITATION_TYPE)
        if precipitation_type is None:
            return None
        return PrecipitationType(precipitation_type).name.lower()

    @property
    def _wind_speed(self):
        """Return the raw wind speed."""
        return self._get_current_property(CC_ATTR_WIND_SPEED)

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._get_current_property(CC_ATTR_WIND_DIRECTION)

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self._get_current_property(CC_ATTR_OZONE)

    @property
    def condition(self):
        """Return the condition."""
        return self._translate_condition(
            self._get_current_property(CC_ATTR_CONDITION),
            is_up(self.hass),
        )

    @property
    def _visibility(self):
        """Return the raw visibility."""
        return self._get_current_property(CC_ATTR_VISIBILITY)

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
            forecast_dt = dt_util.parse_datetime(forecast[CC_ATTR_TIMESTAMP])

            # Throw out past data
            if forecast_dt.date() < dt_util.utcnow().date():
                continue

            values = forecast["values"]
            use_datetime = True

            condition = values.get(CC_ATTR_CONDITION)
            precipitation = values.get(CC_ATTR_PRECIPITATION)
            precipitation_probability = values.get(CC_ATTR_PRECIPITATION_PROBABILITY)

            temp = values.get(CC_ATTR_TEMPERATURE_HIGH)
            temp_low = values.get(CC_ATTR_TEMPERATURE_LOW)
            wind_direction = values.get(CC_ATTR_WIND_DIRECTION)
            wind_speed = values.get(CC_ATTR_WIND_SPEED)

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


class ClimaCellV3WeatherEntity(BaseClimaCellWeatherEntity):
    """Entity that talks to ClimaCell v3 API to retrieve weather data."""

    @staticmethod
    def _translate_condition(
        condition: str | None, sun_is_up: bool = True
    ) -> str | None:
        """Translate ClimaCell condition into an HA condition."""
        if not condition:
            return None
        if "clear" in condition.lower():
            if sun_is_up:
                return CLEAR_CONDITIONS["day"]
            return CLEAR_CONDITIONS["night"]
        return CONDITIONS_V3[condition]

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self._get_cc_value(
            self.coordinator.data[CURRENT], CC_V3_ATTR_TEMPERATURE
        )

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def _pressure(self):
        """Return the raw pressure."""
        return self._get_cc_value(self.coordinator.data[CURRENT], CC_V3_ATTR_PRESSURE)

    @property
    def humidity(self):
        """Return the humidity."""
        return self._get_cc_value(self.coordinator.data[CURRENT], CC_V3_ATTR_HUMIDITY)

    @property
    def wind_gust(self):
        """Return the wind gust speed."""
        return self._get_cc_value(self.coordinator.data[CURRENT], CC_V3_ATTR_WIND_GUST)

    @property
    def cloud_cover(self):
        """Reteurn the cloud cover."""
        return self._get_cc_value(
            self.coordinator.data[CURRENT], CC_V3_ATTR_CLOUD_COVER
        )

    @property
    def precipitation_type(self):
        """Return precipitation type."""
        return self._get_cc_value(
            self.coordinator.data[CURRENT], CC_V3_ATTR_PRECIPITATION_TYPE
        )

    @property
    def _wind_speed(self):
        """Return the raw wind speed."""
        return self._get_cc_value(self.coordinator.data[CURRENT], CC_V3_ATTR_WIND_SPEED)

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._get_cc_value(
            self.coordinator.data[CURRENT], CC_V3_ATTR_WIND_DIRECTION
        )

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self._get_cc_value(self.coordinator.data[CURRENT], CC_V3_ATTR_OZONE)

    @property
    def condition(self):
        """Return the condition."""
        return self._translate_condition(
            self._get_cc_value(self.coordinator.data[CURRENT], CC_V3_ATTR_CONDITION),
            is_up(self.hass),
        )

    @property
    def _visibility(self):
        """Return the raw visibility."""
        return self._get_cc_value(self.coordinator.data[CURRENT], CC_V3_ATTR_VISIBILITY)

    @property
    def forecast(self):
        """Return the forecast."""
        # Check if forecasts are available
        raw_forecasts = self.coordinator.data.get(FORECASTS, {}).get(self.forecast_type)
        if not raw_forecasts:
            return None

        forecasts = []

        # Set default values (in cases where keys don't exist), None will be
        # returned. Override properties per forecast type as needed
        for forecast in raw_forecasts:
            forecast_dt = dt_util.parse_datetime(
                self._get_cc_value(forecast, CC_V3_ATTR_TIMESTAMP)
            )
            use_datetime = True
            condition = self._get_cc_value(forecast, CC_V3_ATTR_CONDITION)
            precipitation = self._get_cc_value(forecast, CC_V3_ATTR_PRECIPITATION)
            precipitation_probability = self._get_cc_value(
                forecast, CC_V3_ATTR_PRECIPITATION_PROBABILITY
            )
            temp = self._get_cc_value(forecast, CC_V3_ATTR_TEMPERATURE)
            temp_low = None
            wind_direction = self._get_cc_value(forecast, CC_V3_ATTR_WIND_DIRECTION)
            wind_speed = self._get_cc_value(forecast, CC_V3_ATTR_WIND_SPEED)

            if self.forecast_type == DAILY:
                use_datetime = False
                forecast_dt = dt_util.start_of_local_day(forecast_dt)
                precipitation = self._get_cc_value(
                    forecast, CC_V3_ATTR_PRECIPITATION_DAILY
                )
                temp = next(
                    (
                        self._get_cc_value(item, CC_V3_ATTR_TEMPERATURE_HIGH)
                        for item in forecast[CC_V3_ATTR_TEMPERATURE]
                        if "max" in item
                    ),
                    temp,
                )
                temp_low = next(
                    (
                        self._get_cc_value(item, CC_V3_ATTR_TEMPERATURE_LOW)
                        for item in forecast[CC_V3_ATTR_TEMPERATURE]
                        if "min" in item
                    ),
                    temp_low,
                )
            elif self.forecast_type == NOWCAST and precipitation:
                # Precipitation is forecasted in CONF_TIMESTEP increments but in a
                # per hour rate, so value needs to be converted to an amount.
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

        return forecasts
