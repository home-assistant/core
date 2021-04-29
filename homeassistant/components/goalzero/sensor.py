"""Support for Goal Zero Yeti Sensors."""
from homeassistant.const import CONF_NAME

from . import YetiEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN, SENSOR_DICT


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Goal Zero Yeti sensor."""
    name = entry.data[CONF_NAME]
    goalzero_data = hass.data[DOMAIN][entry.entry_id]
    sensors = [
        YetiSensor(
            goalzero_data[DATA_KEY_API],
            goalzero_data[DATA_KEY_COORDINATOR],
            name,
            sensor_name,
            entry.entry_id,
        )
        for sensor_name in SENSOR_DICT
    ]
    async_add_entities(sensors)


class YetiSensor(YetiEntity):
    """Representation of a Goal Zero Yeti sensor."""

    def __init__(self, api, coordinator, name, sensor_name, server_unique_id):
        """Initialize a Goal Zero Yeti sensor."""
        super().__init__(api, coordinator, name, server_unique_id)

        self._condition = sensor_name

        variable_info = SENSOR_DICT[sensor_name]
        self._condition_name = variable_info[0]
        self._device_class = variable_info[1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._condition_name}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._condition}"

    @property
    def state(self):
        """Return the state."""
        if self.api.data:
            return self.api.data[self._condition]

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_DICT[self._condition][2]

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return SENSOR_DICT[self._condition][3]
