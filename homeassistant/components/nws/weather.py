"""Support for NWS weather service."""
import asyncio
import logging

import aiohttp

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_PA,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.temperature import convert as convert_temperature

from . import base_unique_id, signal_unique_id
from .const import (
    ATTR_FORECAST_DAYTIME,
    ATTR_FORECAST_DETAILED_DESCRIPTION,
    ATTR_FORECAST_PRECIP_PROB,
    ATTRIBUTION,
    CONDITION_CLASSES,
    CONF_STATION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def convert_condition(time, weather):
    """
    Convert NWS codes to HA condition.

    Choose first condition in CONDITION_CLASSES that exists in weather code.
    If no match is found, return first condition from NWS
    """
    conditions = [w[0] for w in weather]
    prec_probs = [w[1] or 0 for w in weather]

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
            return "sunny", max(prec_probs)
        if time == "night":
            return "clear-night", max(prec_probs)
    return cond, max(prec_probs)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the NWS weather platform."""
    if discovery_info is None:
        return
    latitude = discovery_info.get(CONF_LATITUDE, hass.config.latitude)
    longitude = discovery_info.get(CONF_LONGITUDE, hass.config.longitude)
    station = discovery_info.get(CONF_STATION)

    nws_data = hass.data[DOMAIN][base_unique_id(latitude, longitude)]

    try:
        await nws_data.async_set_station(station)
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.error("Error automatically setting station: %s", str(err))
        raise PlatformNotReady

    await nws_data.async_update()

    async_add_entities(
        [
            NWSWeather(nws_data, "daynight", hass.config.units),
            NWSWeather(nws_data, "hourly", hass.config.units),
        ],
        False,
    )


class NWSWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, nws, mode, units):
        """Initialise the platform with a data instance and station name."""
        self.nws = nws
        self.station = nws.station
        self.latitude = nws.latitude
        self.longitude = nws.longitude

        self.is_metric = units.is_metric
        self.mode = mode

        self.observation = None
        self._forecast = None

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_unique_id(self.latitude, self.longitude),
                self._update_callback,
            )
        )
        self._update_callback()

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self.observation = self.nws.observation
        if self.mode == "daynight":
            self._forecast = self.nws.forecast
        else:
            self._forecast = self.nws.forecast_hourly

        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return False

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the station."""
        return f"{self.station} {self.mode.title()}"

    @property
    def temperature(self):
        """Return the current temperature."""
        temp_c = None
        if self.observation:
            temp_c = self.observation.get("temperature")
        if temp_c:
            return convert_temperature(temp_c, TEMP_CELSIUS, TEMP_FAHRENHEIT)
        return None

    @property
    def pressure(self):
        """Return the current pressure."""
        pressure_pa = None
        if self.observation:
            pressure_pa = self.observation.get("seaLevelPressure")
        if pressure_pa is None:
            return None
        if self.is_metric:
            pressure = convert_pressure(pressure_pa, PRESSURE_PA, PRESSURE_HPA)
            pressure = round(pressure)
        else:
            pressure = convert_pressure(pressure_pa, PRESSURE_PA, PRESSURE_INHG)
            pressure = round(pressure, 2)
        return pressure

    @property
    def humidity(self):
        """Return the name of the sensor."""
        humidity = None
        if self.observation:
            humidity = self.observation.get("relativeHumidity")
        return humidity

    @property
    def wind_speed(self):
        """Return the current windspeed."""
        wind_m_s = None
        if self.observation:
            wind_m_s = self.observation.get("windSpeed")
        if wind_m_s is None:
            return None
        wind_m_hr = wind_m_s * 3600

        if self.is_metric:
            wind = convert_distance(wind_m_hr, LENGTH_METERS, LENGTH_KILOMETERS)
        else:
            wind = convert_distance(wind_m_hr, LENGTH_METERS, LENGTH_MILES)
        return round(wind)

    @property
    def wind_bearing(self):
        """Return the current wind bearing (degrees)."""
        wind_bearing = None
        if self.observation:
            wind_bearing = self.observation.get("windDirection")
        return wind_bearing

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def condition(self):
        """Return current condition."""
        weather = None
        if self.observation:
            weather = self.observation.get("iconWeather")
            time = self.observation.get("iconTime")

        if weather:
            cond, _ = convert_condition(time, weather)
            return cond
        return None

    @property
    def visibility(self):
        """Return visibility."""
        vis_m = None
        if self.observation:
            vis_m = self.observation.get("visibility")
        if vis_m is None:
            return None

        if self.is_metric:
            vis = convert_distance(vis_m, LENGTH_METERS, LENGTH_KILOMETERS)
        else:
            vis = convert_distance(vis_m, LENGTH_METERS, LENGTH_MILES)
        return round(vis, 0)

    @property
    def forecast(self):
        """Return forecast."""
        if self._forecast is None:
            return None
        forecast = []
        for forecast_entry in self._forecast:
            data = {
                ATTR_FORECAST_DETAILED_DESCRIPTION: forecast_entry.get(
                    "detailedForecast"
                ),
                ATTR_FORECAST_TEMP: forecast_entry.get("temperature"),
                ATTR_FORECAST_TIME: forecast_entry.get("startTime"),
            }

            if self.mode == "daynight":
                data[ATTR_FORECAST_DAYTIME] = forecast_entry.get("isDaytime")
            time = forecast_entry.get("iconTime")
            weather = forecast_entry.get("iconWeather")
            if time and weather:
                cond, precip = convert_condition(time, weather)
            else:
                cond, precip = None, None
            data[ATTR_FORECAST_CONDITION] = cond
            data[ATTR_FORECAST_PRECIP_PROB] = precip

            data[ATTR_FORECAST_WIND_BEARING] = forecast_entry.get("windBearing")
            wind_speed = forecast_entry.get("windSpeedAvg")
            if wind_speed:
                if self.is_metric:
                    data[ATTR_FORECAST_WIND_SPEED] = round(
                        convert_distance(wind_speed, LENGTH_MILES, LENGTH_KILOMETERS)
                    )
                else:
                    data[ATTR_FORECAST_WIND_SPEED] = round(wind_speed)
            else:
                data[ATTR_FORECAST_WIND_SPEED] = None
            forecast.append(data)
        return forecast

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{base_unique_id(self.latitude, self.longitude)}_{self.mode}"

    @property
    def available(self):
        """Return if state is available."""
        if self.mode == "daynight":
            return (
                self.nws.update_observation_success and self.nws.update_forecast_success
            )
        return (
            self.nws.update_observation_success
            and self.nws.update_forecast_hourly_success
        )
