"""Support for Goal Zero Yeti Sensors."""
from __future__ import annotations

from homeassistant.components.sensor import ATTR_LAST_RESET, ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
)

from . import YetiEntity
from .const import (
    ATTR_DEFAULT_ENABLED,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    DOMAIN,
    SENSOR_DICT,
)


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
    async_add_entities(sensors, True)


class YetiSensor(YetiEntity):
    """Representation of a Goal Zero Yeti sensor."""

    def __init__(self, api, coordinator, name, sensor_name, server_unique_id):
        """Initialize a Goal Zero Yeti sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self._condition = sensor_name
        sensor = SENSOR_DICT[sensor_name]
        self._attr_device_class = sensor.get(ATTR_DEVICE_CLASS)
        self._attr_entity_registry_enabled_default = sensor.get(ATTR_DEFAULT_ENABLED)
        self._attr_last_reset = sensor.get(ATTR_LAST_RESET)
        self._attr_name = f"{name} {sensor.get(ATTR_NAME)}"
        self._attr_state_class = sensor.get(ATTR_STATE_CLASS)
        self._attr_unique_id = f"{server_unique_id}/{sensor_name}"
        self._attr_unit_of_measurement = sensor.get(ATTR_UNIT_OF_MEASUREMENT)

    @property
    def state(self) -> str | None:
        """Return the state."""
        if self.api.data:
            return self.api.data.get(self._condition)
        return None
