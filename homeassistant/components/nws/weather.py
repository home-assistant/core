"""Support for NWS weather service."""
from datetime import timedelta
import logging

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_SUNNY,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
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
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.dt import utcnow
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.temperature import convert as convert_temperature

from . import base_unique_id
from .const import (
    ATTR_FORECAST_DAYTIME,
    ATTR_FORECAST_DETAILED_DESCRIPTION,
    ATTRIBUTION,
    CONDITION_CLASSES,
    COORDINATOR_FORECAST,
    COORDINATOR_FORECAST_HOURLY,
    COORDINATOR_OBSERVATION,
    DAYNIGHT,
    DOMAIN,
    HOURLY,
    NWS_DATA,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

OBSERVATION_VALID_TIME = timedelta(minutes=20)
FORECAST_VALID_TIME = timedelta(minutes=45)


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
            return ATTR_CONDITION_SUNNY, max(prec_probs)
        if time == "night":
            return ATTR_CONDITION_CLEAR_NIGHT, max(prec_probs)
    return cond, max(prec_probs)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities
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


class NWSWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, entry_data, hass_data, mode, units):
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

        self.is_metric = units.is_metric
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
        wind_km_hr = None
        if self.observation:
            wind_km_hr = self.observation.get("windSpeed")
        if wind_km_hr is None:
            return None

        if self.is_metric:
            wind = wind_km_hr
        else:
            wind = convert_distance(wind_km_hr, LENGTH_KILOMETERS, LENGTH_MILES)
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

            if self.mode == DAYNIGHT:
                data[ATTR_FORECAST_DAYTIME] = forecast_entry.get("isDaytime")
            time = forecast_entry.get("iconTime")
            weather = forecast_entry.get("iconWeather")
            if time and weather:
                cond, precip = convert_condition(time, weather)
            else:
                cond, precip = None, None
            data[ATTR_FORECAST_CONDITION] = cond
            data[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = precip

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

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator_observation.async_request_refresh()
        await self.coordinator_forecast.async_request_refresh()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self.mode == DAYNIGHT
