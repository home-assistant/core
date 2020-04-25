"""Support for the OpenWeatherMap (OWM) service."""
import logging

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
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
    ATTR_API_TEMPERATURE,
    ATTR_API_WEATHER,
    ATTR_API_WEATHER_CODE,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_SPEED,
    ATTRIBUTION,
    DOMAIN,
    ENTRY_FORECAST_COORDINATOR,
    ENTRY_MONITORED_CONDITIONS,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    SENSOR_DEVICE_CLASS,
    SENSOR_NAME,
    SENSOR_UNIT,
)
from .forecast_update_coordinator import ForecastUpdateCoordinator
from .weather_update_coordinator import WeatherUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up OpenWeatherMap sensor entities based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    name = domain_data[ENTRY_NAME]
    weather_coordinator = domain_data[ENTRY_WEATHER_COORDINATOR]
    forecast_coordinator = domain_data[ENTRY_FORECAST_COORDINATOR]
    monitored_conditions = domain_data[ENTRY_MONITORED_CONDITIONS]

    sensor_types = _get_sensor_types(hass.config.units)

    entities = []
    for sensor_type in monitored_conditions:
        unique_id = f"{config_entry.unique_id}-{sensor_type.lower()}"
        entities.append(
            OpenWeatherMapSensor(
                name,
                unique_id,
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
        unique_id,
        sensor_type,
        sensor_types,
        weather_coordinator: WeatherUpdateCoordinator,
        forecast_coordinator: ForecastUpdateCoordinator,
    ):
        """Initialize the sensor."""
        self._name = name
        self._unique_id = unique_id
        self._sensor_type = sensor_type
        self._sensor_name = sensor_types[sensor_type][SENSOR_NAME]
        self._unit_of_measurement = sensor_types[sensor_type][SENSOR_UNIT]
        self._device_class = sensor_types[sensor_type][SENSOR_DEVICE_CLASS]
        self._weather_coordinator = weather_coordinator
        self._forecast_coordinator = forecast_coordinator

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor_name}"

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def device_class(self):
        """Return the device_class."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the device."""
        return self._weather_coordinator.data[self._sensor_type]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

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
        ATTR_API_WEATHER: {
            SENSOR_NAME: "Condition",
            SENSOR_UNIT: None,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_TEMPERATURE: {
            SENSOR_NAME: "Temperature",
            SENSOR_UNIT: units.temperature_unit,
            SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        },
        ATTR_API_WIND_SPEED: {
            SENSOR_NAME: "Wind speed",
            SENSOR_UNIT: SPEED_METERS_PER_SECOND,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_WIND_BEARING: {
            SENSOR_NAME: "Wind bearing",
            SENSOR_UNIT: DEGREE,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_HUMIDITY: {
            SENSOR_NAME: "Humidity",
            SENSOR_UNIT: UNIT_PERCENTAGE,
            SENSOR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        },
        ATTR_API_PRESSURE: {
            SENSOR_NAME: "Pressure",
            SENSOR_UNIT: units.pressure_unit,
            SENSOR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        },
        ATTR_API_CLOUDS: {
            SENSOR_NAME: "Cloud coverage",
            SENSOR_UNIT: UNIT_PERCENTAGE,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_RAIN: {
            SENSOR_NAME: "Rain",
            SENSOR_UNIT: "mm",
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_SNOW: {
            SENSOR_NAME: "Snow",
            SENSOR_UNIT: "mm",
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_WEATHER_CODE: {
            SENSOR_NAME: "Weather code",
            SENSOR_UNIT: None,
            SENSOR_DEVICE_CLASS: None,
        },
    }
