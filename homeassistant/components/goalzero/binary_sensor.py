"""Support for Goal Zero Yeti Sensors."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ICON, ATTR_NAME, CONF_NAME

from . import YetiEntity
from .const import BINARY_SENSOR_DICT, DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Goal Zero Yeti sensor."""
    name = entry.data[CONF_NAME]
    goalzero_data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        YetiBinarySensor(
            goalzero_data[DATA_KEY_API],
            goalzero_data[DATA_KEY_COORDINATOR],
            name,
            sensor_name,
            entry.entry_id,
        )
        for sensor_name in BINARY_SENSOR_DICT
    )


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
        self._attr_device_class = BINARY_SENSOR_DICT[sensor_name].get(ATTR_DEVICE_CLASS)
        self._attr_icon = BINARY_SENSOR_DICT[sensor_name].get(ATTR_ICON)
        self._attr_name = f"{name} {BINARY_SENSOR_DICT[sensor_name].get(ATTR_NAME)}"
        self._attr_unique_id = (
            f"{server_unique_id}/{BINARY_SENSOR_DICT[sensor_name].get(ATTR_NAME)}"
        )

    @property
    def is_on(self) -> bool:
        """Return if the service is on."""
        if self.api.data:
            return self.api.data[self._condition] == 1
        return False
