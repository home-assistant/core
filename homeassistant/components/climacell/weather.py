"""Weather component that handles meteorological data for your location."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Callable

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
    LENGTH_FEET,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.sun import is_up
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util
from homeassistant.util.distance import convert as distance_convert
from homeassistant.util.pressure import convert as pressure_convert

from . import ClimaCellDataUpdateCoordinator, ClimaCellEntity
from .const import (
    CC_ATTR_CONDITION,
    CC_ATTR_HUMIDITY,
    CC_ATTR_OZONE,
    CC_ATTR_PRECIPITATION,
    CC_ATTR_PRECIPITATION_DAILY,
    CC_ATTR_PRECIPITATION_PROBABILITY,
    CC_ATTR_PRESSURE,
    CC_ATTR_TEMPERATURE,
    CC_ATTR_TEMPERATURE_HIGH,
    CC_ATTR_TEMPERATURE_LOW,
    CC_ATTR_TIMESTAMP,
    CC_ATTR_VISIBILITY,
    CC_ATTR_WIND_DIRECTION,
    CC_ATTR_WIND_SPEED,
    CLEAR_CONDITIONS,
    CONDITIONS,
    CONF_TIMESTEP,
    CURRENT,
    DAILY,
    DEFAULT_FORECAST_TYPE,
    DOMAIN,
    FORECASTS,
    HOURLY,
    NOWCAST,
)

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)


def _translate_condition(condition: str | None, sun_is_up: bool = True) -> str | None:
    """Translate ClimaCell condition into an HA condition."""
    if not condition:
        return None
    if "clear" in condition.lower():
        if sun_is_up:
            return CLEAR_CONDITIONS["day"]
        return CLEAR_CONDITIONS["night"]
    return CONDITIONS[condition]


def _forecast_dict(
    hass: HomeAssistantType,
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
        translated_condition = _translate_condition(condition, is_up(hass, forecast_dt))
    else:
        translated_condition = _translate_condition(condition, True)

    if hass.config.units.is_metric:
        if precipitation:
            precipitation = (
                distance_convert(precipitation / 12, LENGTH_FEET, LENGTH_METERS) * 1000
            )
        if wind_speed:
            wind_speed = distance_convert(wind_speed, LENGTH_MILES, LENGTH_KILOMETERS)

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


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        ClimaCellWeatherEntity(config_entry, coordinator, forecast_type)
        for forecast_type in [DAILY, HOURLY, NOWCAST]
    ]
    async_add_entities(entities)


class ClimaCellWeatherEntity(ClimaCellEntity, WeatherEntity):
    """Entity that talks to ClimaCell API to retrieve weather data."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: ClimaCellDataUpdateCoordinator,
        forecast_type: str,
    ) -> None:
        """Initialize ClimaCell weather entity."""
        super().__init__(config_entry, coordinator)
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
        return f"{super().name} - {self.forecast_type.title()}"

    @property
    def unique_id(self) -> str:
        """Return the unique id of the entity."""
        return f"{super().unique_id}_{self.forecast_type}"

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self._get_cc_value(self.coordinator.data[CURRENT], CC_ATTR_TEMPERATURE)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def pressure(self):
        """Return the pressure."""
        pressure = self._get_cc_value(self.coordinator.data[CURRENT], CC_ATTR_PRESSURE)
        if self.hass.config.units.is_metric and pressure:
            return pressure_convert(pressure, PRESSURE_INHG, PRESSURE_HPA)
        return pressure

    @property
    def humidity(self):
        """Return the humidity."""
        return self._get_cc_value(self.coordinator.data[CURRENT], CC_ATTR_HUMIDITY)

    @property
    def wind_speed(self):
        """Return the wind speed."""
        wind_speed = self._get_cc_value(
            self.coordinator.data[CURRENT], CC_ATTR_WIND_SPEED
        )
        if self.hass.config.units.is_metric and wind_speed:
            return distance_convert(wind_speed, LENGTH_MILES, LENGTH_KILOMETERS)
        return wind_speed

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._get_cc_value(
            self.coordinator.data[CURRENT], CC_ATTR_WIND_DIRECTION
        )

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self._get_cc_value(self.coordinator.data[CURRENT], CC_ATTR_OZONE)

    @property
    def condition(self):
        """Return the condition."""
        return _translate_condition(
            self._get_cc_value(self.coordinator.data[CURRENT], CC_ATTR_CONDITION),
            is_up(self.hass),
        )

    @property
    def visibility(self):
        """Return the visibility."""
        visibility = self._get_cc_value(
            self.coordinator.data[CURRENT], CC_ATTR_VISIBILITY
        )
        if self.hass.config.units.is_metric and visibility:
            return distance_convert(visibility, LENGTH_MILES, LENGTH_KILOMETERS)
        return visibility

    @property
    def forecast(self):
        """Return the forecast."""
        # Check if forecasts are available
        if not self.coordinator.data[FORECASTS].get(self.forecast_type):
            return None

        forecasts = []

        # Set default values (in cases where keys don't exist), None will be
        # returned. Override properties per forecast type as needed
        for forecast in self.coordinator.data[FORECASTS][self.forecast_type]:
            forecast_dt = dt_util.parse_datetime(
                self._get_cc_value(forecast, CC_ATTR_TIMESTAMP)
            )
            use_datetime = True
            condition = self._get_cc_value(forecast, CC_ATTR_CONDITION)
            precipitation = self._get_cc_value(forecast, CC_ATTR_PRECIPITATION)
            precipitation_probability = self._get_cc_value(
                forecast, CC_ATTR_PRECIPITATION_PROBABILITY
            )
            temp = self._get_cc_value(forecast, CC_ATTR_TEMPERATURE)
            temp_low = None
            wind_direction = self._get_cc_value(forecast, CC_ATTR_WIND_DIRECTION)
            wind_speed = self._get_cc_value(forecast, CC_ATTR_WIND_SPEED)

            if self.forecast_type == DAILY:
                use_datetime = False
                forecast_dt = dt_util.start_of_local_day(forecast_dt)
                precipitation = self._get_cc_value(
                    forecast, CC_ATTR_PRECIPITATION_DAILY
                )
                temp = next(
                    (
                        self._get_cc_value(item, CC_ATTR_TEMPERATURE_HIGH)
                        for item in forecast[CC_ATTR_TEMPERATURE]
                        if "max" in item
                    ),
                    temp,
                )
                temp_low = next(
                    (
                        self._get_cc_value(item, CC_ATTR_TEMPERATURE_LOW)
                        for item in forecast[CC_ATTR_TEMPERATURE]
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
                _forecast_dict(
                    self.hass,
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
