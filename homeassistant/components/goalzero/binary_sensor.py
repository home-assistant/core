"""Support for Goal Zero Yeti Sensors."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME

from . import YetiEntity
from .const import BINARY_SENSOR_DICT, DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Goal Zero Yeti sensor."""
    name = entry.data[CONF_NAME]
    goalzero_data = hass.data[DOMAIN][entry.entry_id]
    sensors = [
        YetiBinarySensor(
            goalzero_data[DATA_KEY_API],
            goalzero_data[DATA_KEY_COORDINATOR],
            name,
            sensor_name,
            entry.entry_id,
        )
        for sensor_name in BINARY_SENSOR_DICT
    ]
    async_add_entities(sensors, True)


class YetiBinarySensor(YetiEntity, BinarySensorEntity):
    """Representation of a Goal Zero Yeti sensor."""

    def __init__(
        self,
        api,
        coordinator,
        name,
        sensor_name,
        server_unique_id,
    ):
        """Initialize a Goal Zero Yeti sensor."""
        super().__init__(api, coordinator, name, server_unique_id)

        self._condition = sensor_name

        variable_info = BINARY_SENSOR_DICT[sensor_name]
        self._condition_name = variable_info[0]
        self._icon = variable_info[2]
        self._device_class = variable_info[1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._condition_name}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._condition_name}"

    @property
    def is_on(self):
        """Return if the service is on."""
        if self.api.data:
            return self.api.data[self._condition] == 1
        return False

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon
