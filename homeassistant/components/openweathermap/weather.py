"""Support for the OpenWeatherMap (OWM) service."""
import logging

from homeassistant.components.weather import WeatherEntity
from homeassistant.const import TEMP_CELSIUS

from .const import (
    ATTR_API_CONDITION,
    ATTR_API_FORECAST,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_TEMP,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_SPEED,
    ATTRIBUTION,
    CONDITION_CLASSES,
    DOMAIN,
    ENTITY_NAME,
    FORECAST_COORDINATOR,
    WEATHER_COORDINATOR,
)
from .forecast_update_coordinator import ForecastUpdateCoordinator
from .weather_update_coordinator import WeatherUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up OpenWeatherMap weather entity based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    entity_name = domain_data[ENTITY_NAME]
    weather_coordinator = domain_data[WEATHER_COORDINATOR]
    forecast_coordinator = domain_data[FORECAST_COORDINATOR]

    owm_sensor = OpenWeatherMapWeather(
        entity_name, weather_coordinator, forecast_coordinator
    )

    async_add_entities([owm_sensor], False)


class OpenWeatherMapWeather(WeatherEntity):
    """Implementation of an OpenWeatherMap sensor."""

    def __init__(
        self,
        entity_name,
        weather_coordinator: WeatherUpdateCoordinator,
        forecast_coordinator: ForecastUpdateCoordinator,
    ):
        """Initialize the sensor."""
        self._name = entity_name
        self._weather_coordinator = weather_coordinator
        self._forecast_coordinator = forecast_coordinator

    @property
    def condition(self):
        """Return the current condition."""
        return self._weather_coordinator.data[ATTR_API_CONDITION]

    @property
    def temperature(self):
        """Return the temperature."""
        return self._weather_coordinator.data[ATTR_API_TEMP]

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        return self._weather_coordinator.data[ATTR_API_PRESSURE]

    @property
    def humidity(self):
        """Return the humidity."""
        return self._weather_coordinator.data[ATTR_API_HUMIDITY]

    @property
    def wind_speed(self):
        """Return the wind speed."""
        wind_speed = self._weather_coordinator.data[ATTR_API_WIND_SPEED]
        if self.hass.config.units.name == "imperial":
            return round(wind_speed * 2.24, 2)
        return round(wind_speed * 3.6, 2)

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._weather_coordinator.data[ATTR_API_WIND_BEARING]

    @property
    def forecast(self):
        """Return the forecast array."""
        return self._forecast_coordinator.data[ATTR_API_FORECAST]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            self._weather_coordinator.last_update_success
            and self._forecast_coordinator.last_update_success
        )

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self._weather_coordinator.async_add_listener(self.async_write_ha_state)
        self._forecast_coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        self._weather_coordinator.async_remove_listener(self.async_write_ha_state)
        self._forecast_coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self):
        """Get the latest data from OWM and updates the states."""
        await self._weather_coordinator.async_request_refresh()
        await self._forecast_coordinator.async_request_refresh()


def _get_condition(entry):
    return [k for k, v in CONDITION_CLASSES.items() if entry.get_weather_code() in v][0]
