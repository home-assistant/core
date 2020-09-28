"""Abstraction form OWM sensors."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ATTRIBUTION, SENSOR_DEVICE_CLASS, SENSOR_NAME, SENSOR_UNIT

_LOGGER = logging.getLogger(__name__)


class AbstractOpenWeatherMapSensor(Entity):
    """Abstract class for an OpenWeatherMap sensor."""

    def __init__(
        self,
        name,
        unique_id,
        sensor_type,
        sensor_configuration,
        coordinator: DataUpdateCoordinator,
    ):
        """Initialize the sensor."""
        self._name = name
        self._unique_id = unique_id
        self._sensor_type = sensor_type
        self._sensor_name = sensor_configuration[SENSOR_NAME]
        self._unit_of_measurement = sensor_configuration.get(SENSOR_UNIT)
        self._device_class = sensor_configuration.get(SENSOR_DEVICE_CLASS)
        self._coordinator = coordinator

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
        return self._coordinator.last_update_success

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Get the latest data from OWM and updates the states."""
        await self._coordinator.async_request_refresh()
