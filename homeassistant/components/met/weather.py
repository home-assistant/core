"""Support for Met.no weather service."""
import logging
from random import randrange
from datetime import timedelta
import async_timeout
import voluptuous as vol

from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    EVENT_CORE_CONFIG_UPDATE,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.util.distance import convert as convert_distance
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.pressure import convert as convert_pressure

from .const import DOMAIN, CONF_TRACK_HOME

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
    """Set up the Met.no weather platform.
    TBD: Can this be removed? If not, should this also contain the Update Coordinator"""
    _LOGGER.error("Loading Met.no via platform config is deprecated")


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    unique_id = (
        f"{config_entry.data[CONF_LATITUDE]}-{config_entry.data[CONF_LONGITUDE]}"
    )

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            return await hass.data[DOMAIN][unique_id].fetch_data()
        except Exception as e:
            raise UpdateFailed(f"Update failed: {e}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=unique_id,
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(minutes=randrange(55, 65)),
    )

    # Fetch initial data so we have data when entities subscribe
    hass.data[DOMAIN][unique_id].init_data()
    await hass.data[DOMAIN][unique_id].fetch_data()

    async_add_entities(
        [MetWeather(coordinator, config_entry.data, hass.config.units.is_metric)]
    )


class MetWeather(WeatherEntity):
    """Implementation of a Met.no weather condition."""

    def __init__(self, coordinator, config, is_metric):
        """Initialise the platform with a data instance and site."""
        self._config = config
        self._coordinator = coordinator
        # TBD: For _core_config_updated: remember current unique_id, to be able to find whether data when coordinations change
        # self._unique_id = f"{config[CONF_LATITUDE]}-{config[CONF_LONGITUDE]}"
        self._is_metric = is_metric
        self._unsub_track_home = None

    async def async_added_to_hass(self):
        """Start fetching data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
        if self._config.get(CONF_TRACK_HOME):
            self._unsub_track_home = self.hass.bus.async_listen(
                EVENT_CORE_CONFIG_UPDATE, self._core_config_updated
            )
        await self.async_update()

    async def _core_config_updated(self, _event):
        """Handle core config updated.
        TBD: If the latitude or longitude changed, re-create the WeatherData
        I have no idea how this Home tracking works"""
        # del self.hass.data[DOMAIN][self.unique_id]
        # self._unique_id = f"{config[CONF_LATITUDE]}-{config[CONF_LONGITUDE]}"
        # self.hass.data[DOMAIN][self.unique_id] = MetWeatherData(config, self.hass.config.units.is_metric)
        # self.hass.data[DOMAIN][self.unique_id].init_data()
        # await self.hass.data[DOMAIN][self.unique_id].fetch_data()
        pass

    async def will_remove_from_hass(self):
        """Handle entity will be removed from hass."""
        if self._unsub_track_home:
            self._unsub_track_home()
            self._unsub_track_home = None

    async def async_update(self):
        """Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()
        self.async_write_ha_state()

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
            return "home"

        return f"{self._config[CONF_LATITUDE]}-{self._config[CONF_LONGITUDE]}"

    @property
    def name(self):
        """Return the name of the sensor."""
        name = self._config.get(CONF_NAME)

        if name is not None:
            return name

        if self.track_home:
            return self.hass.config.location_name

        return DEFAULT_NAME

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
        return self._coordinator.data.forecast_data
