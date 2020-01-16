"""Initialization of ATAG One sensor platform."""
from homeassistant.const import CONF_SENSORS

from . import DOMAIN, AtagEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Atag updated to use config entry."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Initialize sensor platform from config entry."""
    sensors = config_entry.data.get(CONF_SENSORS)
    if not sensors:
        return
    atag = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for sensor in map(str.lower, sensors):
        entities.append(AtagOneSensor(atag, sensor))
    async_add_entities(entities)


class AtagOneSensor(AtagEntity):
    """Representation of a AtagOne Sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Get latest data from datastore."""
        data = self.atag.sensordata.get(self._datafield)
        if isinstance(data, list):
            self._state, self._icon = data
        else:
            self._state = data
