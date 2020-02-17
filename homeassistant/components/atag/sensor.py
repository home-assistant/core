"""Initialization of ATAG One sensor platform."""
from homeassistant.const import ATTR_ICON, ATTR_STATE

from . import DOMAIN, ENTITY_TYPES, SENSOR, AtagEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Atag updated to use config entry."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Initialize sensor platform from config entry."""
    atag = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for sensor in ENTITY_TYPES[SENSOR]:
        entities.append(AtagSensor(atag, ENTITY_TYPES[SENSOR][sensor]))
    async_add_entities(entities)


class AtagSensor(AtagEntity):
    """Representation of a AtagOne Sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._sensor_value

    async def async_update(self):
        """Get latest data from datastore."""
        data = self.atag.sensordata.get(self._id)
        if data:
            self._sensor_value = data.get(ATTR_STATE)
            self._icon = data.get(ATTR_ICON) or self._icon
