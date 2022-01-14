"""Support for Xiaomi Aqara sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import TEMP_CELSIUS

from .const import DOMAIN
from .device import YoLinkDevice

_LOGGER = logging.getLogger(__name__)
SENSOR_TYPES = {
    "DoorSensor": [None, None, "door"],
    "LeakSensor": [None, None, "moisture"],
    "MotionSensor": [None, None, "motion"],
    "TSensor": [TEMP_CELSIUS, None, "temperature"],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Xiaomi devices."""
    entities = []
    for device in hass.data[DOMAIN][config_entry.entry_id]["devices"]:
        if device["type"] == "DoorSensor":
            entities.append(YoLinkDoorSensor(device, config_entry))
        elif device["type"] == "LeakSensor":
            entities.append(YoLinkLeakSensor(device, config_entry))
        elif device["type"] == "MotionSensor":
            entities.append(YoLinkMotionSensor(device, config_entry))
        elif device["type"] == "THSensor":
            entities.append(YoLinkTemperatureSensor(device, config_entry))
    async_add_entities(entities)


class YoLinkSensor(YoLinkDevice, SensorEntity):
    """Representation of a YoLink Sensor."""

    def __init__(self, device, device_type, config_entry):
        """Initialize the YoLink Sensor."""
        super().__init__(device, device_type, config_entry)

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        try:
            return SENSOR_TYPES.get(self._type)[1]
        except TypeError:
            return None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        try:
            return SENSOR_TYPES.get(self._type)[0]
        except TypeError:
            return None

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return SENSOR_TYPES.get(self._type)[2] if self._type in SENSOR_TYPES else None


class YoLinkBinarySensor(YoLinkDevice, BinarySensorEntity):
    """Representation of a YoLink Sensor."""

    @property
    def device_class(self):
        """Class type of device."""
        if self._type in SENSOR_TYPES:
            return SENSOR_TYPES.get(self._type)[2]
        raise NotImplementedError("Binary Sensor not implemented:" + self._type)

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return False


class YoLinkDoorSensor(YoLinkBinarySensor):
    """YoLink Door Sensor Instance."""

    def __init__(self, device, config_entry):
        """Initialize the YoLink Door Sensor."""
        super().__init__(device, "DoorSensor", config_entry)

    def parse_state(self, state):
        """Parse Door Sensor state from data."""
        self._attr_is_on = state["state"]["state"] == "alert"


class YoLinkLeakSensor(YoLinkBinarySensor):
    """YoLink Leak Sensor Instance."""

    def __init__(self, device, config_entry):
        """Initialize the YoLink Leak Sensor."""
        super().__init__(device, "LeakSensor", config_entry)

    def parse_state(self, state):
        """Parse Leak Sensor state from data."""
        self._attr_is_on = (
            state["state"]["state"] == "alert" or state["state"]["state"] == "full"
        )


class YoLinkMotionSensor(YoLinkBinarySensor):
    """YoLink Motion Sensor Instance."""

    def __init__(self, device, config_entry):
        """Initialize the YoLink Motion Sensor."""
        super().__init__(device, "MotionSensor", config_entry)

    def parse_state(self, state):
        """Parse Motion Sensor state from data."""
        self._attr_is_on = state["state"]["state"] == "alert"


class YoLinkTemperatureSensor(YoLinkSensor):
    """YoLink T&H Sensor Instance."""

    def __init__(self, device, config_entry):
        """Initialize the ofYoLink T&H Sensor."""
        super().__init__(device, "temperature", config_entry)

    def parse_state(self, state):
        """Parse T&H Sensor state from data."""
        self._attr_native_value = state["state"]["temperature"]
