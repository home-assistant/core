"""Support for Met.no weather service."""
import logging

import voluptuous as vol

from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_CELSIUS,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure

from .const import CONF_TRACK_HOME, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = (
    "Weather forecast from met.no, delivered by the Norwegian "
    "Meteorological Institute."
)
DEFAULT_NAME = "Met.no"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
        vol.Optional(CONF_ELEVATION): int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Met.no weather platform."""
    _LOGGER.warning("Loading Met.no via platform config is deprecated")

    # Add defaults.
    config = {CONF_ELEVATION: hass.config.elevation, **config}

    if config.get(CONF_LATITUDE) is None:
        config[CONF_TRACK_HOME] = True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            MetWeather(
                coordinator, config_entry.data, hass.config.units.is_metric, False
            ),
            MetWeather(
                coordinator, config_entry.data, hass.config.units.is_metric, True
            ),
        ]
    )


class MetWeather(WeatherEntity):
    """Implementation of a Met.no weather condition."""

    def __init__(self, coordinator, config, is_metric, hourly):
        """Initialise the platform with a data instance and site."""
        self._config = config
        self._coordinator = coordinator
        self._is_metric = is_metric
        self._hourly = hourly
        self._name_appendix = "-hourly" if hourly else ""

    async def async_added_to_hass(self):
        """Start fetching data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Only used by the generic entity update service."""
        await self._coordinator.async_request_refresh()

    @property
    def track_home(self):
        """Return if we are tracking home."""
        return self._config.get(CONF_TRACK_HOME, False)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return unique ID."""
        if self.track_home:
            return f"home{self._name_appendix}"

        return f"{self._config[CONF_LATITUDE]}-{self._config[CONF_LONGITUDE]}{self._name_appendix}"

    @property
    def name(self):
        """Return the name of the sensor."""
        name = self._config.get(CONF_NAME)

        if name is not None:
            return f"{name}{self._name_appendix}"

        if self.track_home:
            return f"{self.hass.config.location_name}{self._name_appendix}"

        return f"{DEFAULT_NAME}{self._name_appendix}"

    @property
    def condition(self):
        """Return the current condition."""
        return self._coordinator.data.current_weather_data.get("condition")

    @property
    def temperature(self):
        """Return the temperature."""
        return self._coordinator.data.current_weather_data.get("temperature")

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        pressure_hpa = self._coordinator.data.current_weather_data.get("pressure")
        if self._is_metric or pressure_hpa is None:
            return pressure_hpa

        return round(convert_pressure(pressure_hpa, PRESSURE_HPA, PRESSURE_INHG), 2)

    @property
    def humidity(self):
        """Return the humidity."""
        return self._coordinator.data.current_weather_data.get("humidity")

    @property
    def wind_speed(self):
        """Return the wind speed."""
        speed_m_s = self._coordinator.data.current_weather_data.get("wind_speed")
        if self._is_metric or speed_m_s is None:
            return speed_m_s

        speed_mi_s = convert_distance(speed_m_s, LENGTH_METERS, LENGTH_MILES)
        speed_mi_h = speed_mi_s / 3600.0
        return int(round(speed_mi_h))

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return self._coordinator.data.current_weather_data.get("wind_bearing")

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        if self._hourly:
            return self._coordinator.data.hourly_forecast
        return self._coordinator.data.daily_forecast
