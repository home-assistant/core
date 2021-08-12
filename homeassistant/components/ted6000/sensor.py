"""Support gathering ted6000 information."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN, NAME, SENSORS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up envoy sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data[COORDINATOR]
    name = data[NAME]

    entities = []
    for sensor_description in SENSORS:
        entity_name = f"{name} {sensor_description.name}"
        entities.append(
            Ted6000Sensor(
                sensor_description, entity_name, config_entry.unique_id, coordinator
            )
        )

    async_add_entities(entities)
    return True


class Ted6000Sensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Ted6000 sensor."""

    def __init__(self, description, name, device_id, coordinator):
        """Initialize the sensor."""
        self.entity_description = description
        self._device_id = device_id
        self._name = name

        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:flash"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._device_id}_{self.entity_description.key}"

    @property
    def state(self):
        """Return the state of the resources."""
        return self.coordinator.data.get(self.entity_description.key)
