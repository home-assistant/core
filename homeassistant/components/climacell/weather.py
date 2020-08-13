"""Weather component that handles meteorological data for your location."""
import logging
from typing import Any, Callable, Dict, List, Optional, Union

import pytz

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
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.sun import is_up
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util
from homeassistant.util.distance import convert as distance_convert
from homeassistant.util.pressure import convert as pressure_convert
from homeassistant.util.temperature import convert as temp_convert

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
    CONF_FORECAST_TYPE,
    CONF_TIMESTEP,
    CURRENT,
    DAILY,
    DOMAIN,
    FORECASTS,
    HOURLY,
    NOWCAST,
    WIND_DIRECTIONS,
)

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)


def _translate_condition(
    condition: Optional[str], sun_is_up: bool = True
) -> Optional[str]:
    """Translate ClimaCell condition into an HA condition."""
    if not condition:
        return None
    if "clear" in condition.lower():
        if sun_is_up:
            return CLEAR_CONDITIONS["day"]
        return CLEAR_CONDITIONS["night"]
    return CONDITIONS[condition]


def _translate_wind_direction(direction: Optional[float]) -> Optional[str]:
    """Translate ClimaCell wind direction in degrees to a bearing."""
    if direction:
        return WIND_DIRECTIONS.get(int(direction * 16 / 360))
    return None


def _forecast_dict(
    hass: HomeAssistantType,
    time: str,
    use_datetime: bool,
    condition: str,
    precipitation: Optional[float],
    precipitation_probability: Optional[float],
    temp: Optional[float],
    temp_low: Optional[float],
    wind_direction: Optional[float],
    wind_speed: Optional[float],
) -> Dict[str, Any]:
    """Return formatted Forecast dict from ClimaCell forecast data."""
    wind_bearing = _translate_wind_direction(wind_direction)
    if use_datetime:
        translated_condition = _translate_condition(
            condition,
            is_up(hass, dt_util.parse_datetime(time).replace(tzinfo=pytz.utc)),
        )
    else:
        translated_condition = _translate_condition(condition, True)

    if not hass.config.units.is_metric:
        data = {
            ATTR_FORECAST_TIME: time,
            ATTR_FORECAST_CONDITION: translated_condition,
            ATTR_FORECAST_PRECIPITATION: precipitation,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: precipitation_probability,
            ATTR_FORECAST_TEMP: temp,
            ATTR_FORECAST_TEMP_LOW: temp_low,
            ATTR_FORECAST_WIND_BEARING: wind_bearing,
            ATTR_FORECAST_WIND_SPEED: wind_speed,
        }
    else:
        data = {
            ATTR_FORECAST_TIME: time,
            ATTR_FORECAST_CONDITION: translated_condition,
            ATTR_FORECAST_PRECIPITATION: distance_convert(
                precipitation / 12, LENGTH_FEET, LENGTH_METERS
            )
            * 1000
            if precipitation
            else None,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: precipitation_probability,
            ATTR_FORECAST_TEMP: temp_convert(temp, TEMP_FAHRENHEIT, TEMP_CELSIUS)
            if temp
            else None,
            ATTR_FORECAST_TEMP_LOW: temp_convert(
                temp_low, TEMP_FAHRENHEIT, TEMP_CELSIUS
            )
            if temp_low
            else None,
            ATTR_FORECAST_WIND_BEARING: wind_bearing,
            ATTR_FORECAST_WIND_SPEED: distance_convert(
                wind_speed, LENGTH_MILES, LENGTH_KILOMETERS
            )
            if wind_speed
            else None,
        }

    return {k: v for k, v in data.items() if v is not None}


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entity = ClimaCellWeatherEntity(config_entry, coordinator)

    async_add_entities([entity], update_before_add=True)


class ClimaCellWeatherEntity(ClimaCellEntity, WeatherEntity):
    """Entity that talks to ClimaCell API to retrieve weather data."""

    def __init__(
        self, config_entry: ConfigEntry, coordinator: ClimaCellDataUpdateCoordinator
    ) -> None:
        """Initialize ClimaCell Entity."""
        self._data_current = {}
        self._data_forecasts = []
        super().__init__(config_entry, coordinator)

    def refresh_state(self) -> None:
        """Refresh state for entity after DataUpdateCoordinator update."""
        self._data_current = self._coordinator.data[CURRENT]
        self._data_forecasts = self._coordinator.data[FORECASTS]
        self.async_write_ha_state()

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self._get_cc_value(self._data_current, CC_ATTR_TEMPERATURE)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def pressure(self):
        """Return the pressure."""
        pressure = self._get_cc_value(self._data_current, CC_ATTR_PRESSURE)
        if self.hass.config.units.is_metric and pressure:
            return pressure_convert(pressure, PRESSURE_INHG, PRESSURE_HPA)
        return pressure

    @property
    def humidity(self):
        """Return the humidity."""
        humidity = self._get_cc_value(self._data_current, CC_ATTR_HUMIDITY)
        return humidity / 100 if humidity else None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        wind_speed = self._get_cc_value(self._data_current, CC_ATTR_WIND_SPEED)
        if self.hass.config.units.is_metric and wind_speed:
            return distance_convert(wind_speed, LENGTH_MILES, LENGTH_KILOMETERS)
        return wind_speed

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return _translate_wind_direction(
            self._get_cc_value(self._data_current, CC_ATTR_WIND_DIRECTION)
        )

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self._get_cc_value(self._data_current, CC_ATTR_OZONE)

    @property
    def condition(self):
        """Return the condition."""
        return _translate_condition(
            self._get_cc_value(self._data_current, CC_ATTR_CONDITION), is_up(self.hass),
        )

    @property
    def visibility(self):
        """Return the visibility."""
        visibility = self._get_cc_value(self._data_current, CC_ATTR_VISIBILITY)
        if self.hass.config.units.is_metric and visibility:
            return distance_convert(visibility, LENGTH_MILES, LENGTH_KILOMETERS)
        return visibility

    @property
    def forecast(self):
        """Return the forecast."""
        forecasts = []

        if (
            self._config_entry.data[CONF_FORECAST_TYPE] == DAILY
            and self._data_forecasts
        ):
            for forecast in self._data_forecasts:
                temp_max = None
                temp_min = None
                for item in forecast[CC_ATTR_TEMPERATURE]:
                    if "max" in item:
                        temp_max = self._get_cc_value(item, CC_ATTR_TEMPERATURE_HIGH)
                    if "min" in item:
                        temp_min = self._get_cc_value(item, CC_ATTR_TEMPERATURE_LOW)
                forecasts.append(
                    _forecast_dict(
                        self.hass,
                        self._get_cc_value(forecast, CC_ATTR_TIMESTAMP),
                        False,
                        self._get_cc_value(forecast, CC_ATTR_CONDITION),
                        self._get_cc_value(forecast, CC_ATTR_PRECIPITATION_DAILY),
                        self._get_cc_value(forecast, CC_ATTR_PRECIPITATION_PROBABILITY)
                        / 100,
                        temp_max,
                        temp_min,
                        None,
                        None,
                    )
                )
            return forecasts

        if (
            self._config_entry.data[CONF_FORECAST_TYPE] == HOURLY
            and self._data_forecasts
        ):
            for forecast in self._data_forecasts:
                forecasts.append(
                    _forecast_dict(
                        self.hass,
                        self._get_cc_value(forecast, CC_ATTR_TIMESTAMP),
                        True,
                        self._get_cc_value(forecast, CC_ATTR_CONDITION),
                        self._get_cc_value(forecast, CC_ATTR_PRECIPITATION),
                        self._get_cc_value(forecast, CC_ATTR_PRECIPITATION_PROBABILITY)
                        / 100,
                        self._get_cc_value(forecast, CC_ATTR_TEMPERATURE),
                        None,
                        self._get_cc_value(forecast, CC_ATTR_WIND_DIRECTION),
                        self._get_cc_value(forecast, CC_ATTR_WIND_SPEED),
                    )
                )
            return forecasts

        if (
            self._config_entry.data[CONF_FORECAST_TYPE] == NOWCAST
            and self._data_forecasts
        ):
            for forecast in self._data_forecasts:
                # Precipitation is forecasted in CONF_TIMESTEP increments
                # but per hour, so this converts to an amount
                precipitation: Optional[Union[float, int]] = self._get_cc_value(
                    forecast, CC_ATTR_PRECIPITATION
                )
                precipitation = (
                    precipitation / 60 * self._config_entry.options[CONF_TIMESTEP]
                    if precipitation
                    else None
                )
                forecasts.append(
                    _forecast_dict(
                        self.hass,
                        self._get_cc_value(forecast, CC_ATTR_TIMESTAMP),
                        True,
                        self._get_cc_value(forecast, CC_ATTR_CONDITION),
                        precipitation,
                        None,
                        self._get_cc_value(forecast, CC_ATTR_TEMPERATURE),
                        None,
                        self._get_cc_value(forecast, CC_ATTR_WIND_DIRECTION),
                        self._get_cc_value(forecast, CC_ATTR_WIND_SPEED),
                    )
                )
            return forecasts

        return None
