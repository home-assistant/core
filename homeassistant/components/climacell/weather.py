"""Weather component that handles meteorological data for your location."""
import logging
from typing import Any, Callable, Dict, List, Optional

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

from . import ClimaCellEntity
from .const import (
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
    precipitation: str,
    precipitation_probability: Optional[float],
    temp: float,
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
            * 1000,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: precipitation_probability,
            ATTR_FORECAST_TEMP: temp_convert(temp, TEMP_FAHRENHEIT, TEMP_CELSIUS),
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

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self._coordinator.data[CURRENT].get("temp", {}).get("value")

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def pressure(self):
        """Return the pressure."""
        pressure = self._coordinator.data[CURRENT].get("baro_pressure", {}).get("value")
        if self.hass.config.units.is_metric and pressure:
            return pressure_convert(pressure, PRESSURE_INHG, PRESSURE_HPA)
        return pressure

    @property
    def humidity(self):
        """Return the humidity."""
        humidity = self._coordinator.data[CURRENT].get("humidity", {}).get("value")
        return humidity / 100 if humidity else None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        wind_speed = self._coordinator.data[CURRENT].get("wind_speed", {}).get("value")
        if self.hass.config.units.is_metric and wind_speed:
            return distance_convert(wind_speed, LENGTH_MILES, LENGTH_KILOMETERS)
        return wind_speed

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return _translate_wind_direction(
            self._coordinator.data[CURRENT].get("wind_direction", {}).get("value")
        )

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self._coordinator.data[CURRENT].get("o3", {}).get("value")

    @property
    def condition(self):
        """Return the condition."""
        return _translate_condition(
            self._coordinator.data[CURRENT].get("weather_code", {}).get("value"),
            is_up(self.hass),
        )

    @property
    def visibility(self):
        """Return the visibility."""
        visibility = self._coordinator.data[CURRENT].get("visibility", {}).get("value")
        if self.hass.config.units.is_metric and visibility:
            return distance_convert(visibility, LENGTH_MILES, LENGTH_KILOMETERS)
        return visibility

    @property
    def forecast(self):
        """Return the forecast."""
        forecasts = []

        if (
            self._config_entry.data[CONF_FORECAST_TYPE] == DAILY
            and self._coordinator.data[FORECASTS]
        ):
            for forecast in self._coordinator.data[FORECASTS]:
                temp_max = None
                temp_min = None
                for item in forecast["temp"]:
                    if "max" in item:
                        temp_max = item["max"]["value"]
                    if "min" in item:
                        temp_min = item["min"]["value"]
                forecasts.append(
                    _forecast_dict(
                        self.hass,
                        forecast["observation_time"]["value"],
                        True,
                        forecast["weather_code"]["value"],
                        forecast["precipitation_accumulation"]["value"],
                        forecast["precipitation_probability"]["value"] / 100,
                        temp_max,
                        temp_min,
                        None,
                        None,
                    )
                )
            return forecasts

        if (
            self._config_entry.data[CONF_FORECAST_TYPE] == HOURLY
            and self._coordinator.data[FORECASTS]
        ):
            for forecast in self._coordinator.data[FORECASTS]:
                forecasts.append(
                    _forecast_dict(
                        self.hass,
                        forecast["observation_time"]["value"],
                        False,
                        forecast["weather_code"]["value"],
                        forecast["precipitation"]["value"],
                        forecast["precipitation_probability"]["value"] / 100,
                        forecast["temp"]["value"],
                        None,
                        forecast["wind_direction"]["value"],
                        forecast["wind_speed"]["value"],
                    )
                )
            return forecasts

        if (
            self._config_entry.data[CONF_FORECAST_TYPE] == NOWCAST
            and self._coordinator.data[FORECASTS]
        ):
            for forecast in self._coordinator.data[FORECASTS]:
                forecasts.append(
                    _forecast_dict(
                        self.hass,
                        forecast["observation_time"]["value"],
                        True,
                        forecast["weather_code"]["value"],
                        (
                            forecast["precipitation"]["value"]
                            * self._config_entry.options[CONF_TIMESTEP]
                            / 60
                        ),
                        None,
                        forecast["temp"]["value"],
                        None,
                        forecast["wind_direction"]["value"],
                        forecast["wind_speed"]["value"],
                    )
                )
            return forecasts

        return None
