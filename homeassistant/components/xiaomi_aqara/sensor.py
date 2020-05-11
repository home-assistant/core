"""Support for Xiaomi Aqara sensors."""
import logging

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)

from . import XiaomiDevice
from .config_flow import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "temperature": [TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE],
    "humidity": [UNIT_PERCENTAGE, None, DEVICE_CLASS_HUMIDITY],
    "illumination": ["lm", None, DEVICE_CLASS_ILLUMINANCE],
    "lux": ["lx", None, DEVICE_CLASS_ILLUMINANCE],
    "pressure": ["hPa", None, DEVICE_CLASS_PRESSURE],
    "bed_activity": ["μm", None, None],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Xiaomi devices."""
    entities = []
    gateway = hass.data[DOMAIN][config_entry.entry_id]
    for entity in gateway.devices["sensor"]:
        if entity["model"] == "sensor_ht":
            entities.append(
                XiaomiSensor(entity, "Temperature", "temperature", gateway)
            )
            entities.append(XiaomiSensor(entity, "Humidity", "humidity", gateway))
        elif entity["model"] in ["weather", "weather.v1"]:
            entities.append(
                XiaomiSensor(entity, "Temperature", "temperature", gateway)
            )
            entities.append(XiaomiSensor(entity, "Humidity", "humidity", gateway))
            entities.append(XiaomiSensor(entity, "Pressure", "pressure", gateway))
        elif entity["model"] == "sensor_motion.aq2":
            entities.append(XiaomiSensor(entity, "Illumination", "lux", gateway))
        elif entity["model"] in ["gateway", "gateway.v3", "acpartner.v3"]:
            entities.append(
                XiaomiSensor(entity, "Illumination", "illumination", gateway)
            )
        elif entity["model"] in ["vibration"]:
            entities.append(
                XiaomiSensor(entity, "Bed Activity", "bed_activity", gateway)
            )
            entities.append(
                XiaomiSensor(entity, "Tilt Angle", "final_tilt_angle", gateway)
            )
            entities.append(
                XiaomiSensor(entity, "Coordination", "coordination", gateway)
            )
        else:
            _LOGGER.warning("Unmapped Device Model ")
    async_add_entities(entities)


class XiaomiSensor(XiaomiDevice):
    """Representation of a XiaomiSensor."""

    def __init__(self, device, name, data_key, xiaomi_hub):
        """Initialize the XiaomiSensor."""
        self._data_key = data_key
        XiaomiDevice.__init__(self, device, name, xiaomi_hub)

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        try:
            return SENSOR_TYPES.get(self._data_key)[1]
        except TypeError:
            return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        try:
            return SENSOR_TYPES.get(self._data_key)[0]
        except TypeError:
            return None

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return (
            SENSOR_TYPES.get(self._data_key)[2]
            if self._data_key in SENSOR_TYPES
            else None
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        value = data.get(self._data_key)
        if value is None:
            return False
        if self._data_key in ["coordination", "status"]:
            self._state = value
            return True
        value = float(value)
        if self._data_key in ["temperature", "humidity", "pressure"]:
            value /= 100
        elif self._data_key in ["illumination"]:
            value = max(value - 300, 0)
        if self._data_key == "temperature" and (value < -50 or value > 60):
            return False
        if self._data_key == "humidity" and (value <= 0 or value > 100):
            return False
        if self._data_key == "pressure" and value == 0:
            return False
        if self._data_key in ["illumination", "lux"]:
            self._state = round(value)
        else:
            self._state = round(value, 1)
        return True
