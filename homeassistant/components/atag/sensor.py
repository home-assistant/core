"""Initialization of ATAG One sensor platform."""
from . import DOMAIN, AtagEntity

DEFAULT_SENSORS = [
    "outside_temp",
    "outside_temp_avg",
    "weather_status",
    "operation_mode",
    "ch_water_pressure",
    "dhw_water_temp",
    "burning_hours",
    "flame_level",
]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Atag updated to use config entry."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Initialize sensor platform from config entry."""
    atag = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for sensor in DEFAULT_SENSORS:
        entities.append(AtagSensor(atag, sensor))
    async_add_entities(entities)


class AtagSensor(AtagEntity):
    """Representation of a AtagOne Sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Get latest data from datastore."""
        data = self.atag.sensordata.get(self._datafield)
        if data:
            self._state = data.get("state")
            self._icon = data.get("icon") or self._icon
