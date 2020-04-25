"""Support for the OpenWeatherMap (OWM) service."""
import logging

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEGREE,
    SPEED_METERS_PER_SECOND,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_API_CLOUDS,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_RAIN,
    ATTR_API_SNOW,
    ATTR_API_TEMP,
    ATTR_API_WEATHER,
    ATTR_API_WEATHER_CODE,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_SPEED,
    ATTRIBUTION,
    DOMAIN,
    ENTRY_ENTITY_NAME,
    ENTRY_FORECAST_COORDINATOR,
    ENTRY_MONITORED_CONDITIONS,
    ENTRY_WEATHER_COORDINATOR,
)
from .forecast_update_coordinator import ForecastUpdateCoordinator
from .weather_update_coordinator import WeatherUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up OpenWeatherMap sensor entities based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    entity_name = domain_data[ENTRY_ENTITY_NAME]
    weather_coordinator = domain_data[ENTRY_WEATHER_COORDINATOR]
    forecast_coordinator = domain_data[ENTRY_FORECAST_COORDINATOR]
    monitored_conditions = domain_data[ENTRY_MONITORED_CONDITIONS]

    sensor_types = _get_sensor_types(hass.config.units)

    entities = []
    for sensor_type in monitored_conditions:
        entities.append(
            OpenWeatherMapSensor(
                entity_name,
                sensor_type,
                sensor_types,
                weather_coordinator,
                forecast_coordinator,
            )
        )

    async_add_entities(entities, False)


class OpenWeatherMapSensor(Entity):
    """Implementation of an OpenWeatherMap sensor."""

    def __init__(
        self,
        name,
        sensor_type,
        sensor_types,
        weather_coordinator: WeatherUpdateCoordinator,
        forecast_coordinator: ForecastUpdateCoordinator,
    ):
        """Initialize the sensor."""
        self._name = name
        self._sensor_name = sensor_types[sensor_type][0]
        self._unit_of_measurement = sensor_types[sensor_type][1]
        self._attr_key = sensor_types[sensor_type][2]
        self._weather_coordinator = weather_coordinator
        self._forecast_coordinator = forecast_coordinator

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor_name}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._weather_coordinator.data[self._attr_key]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

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


def _get_sensor_types(units):
    return {
        "weather": ["Condition", None, ATTR_API_WEATHER],
        "temperature": ["Temperature", units.temperature_unit, ATTR_API_TEMP],
        "wind_speed": ["Wind speed", SPEED_METERS_PER_SECOND, ATTR_API_WIND_SPEED],
        "wind_bearing": ["Wind bearing", DEGREE, ATTR_API_WIND_BEARING],
        "humidity": ["Humidity", UNIT_PERCENTAGE, ATTR_API_HUMIDITY],
        "pressure": ["Pressure", units.pressure_unit, ATTR_API_PRESSURE],
        "clouds": ["Cloud coverage", UNIT_PERCENTAGE, ATTR_API_CLOUDS],
        "rain": ["Rain", "mm", ATTR_API_RAIN],
        "snow": ["Snow", "mm", ATTR_API_SNOW],
        "weather_code": ["Weather code", None, ATTR_API_WEATHER_CODE],
    }
