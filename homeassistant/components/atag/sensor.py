"""Initialization of ATAG One sensor platform."""
from homeassistant.const import ATTR_STATE

from . import DOMAIN, ENTITY_TYPES, SENSOR, AtagEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Initialize sensor platform from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for sensor in ENTITY_TYPES[SENSOR]:
        entities.append(AtagSensor(coordinator, sensor))
    async_add_entities(entities)


class AtagSensor(AtagEntity):
    """Representation of a AtagOne Sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self._id][ATTR_STATE]
