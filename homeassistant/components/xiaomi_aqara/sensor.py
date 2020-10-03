"""Support for Xiaomi Aqara sensors."""
import logging

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
)

from . import XiaomiDevice
from .const import BATTERY_MODELS, DOMAIN, GATEWAYS_KEY, POWER_MODELS

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "temperature": [TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE],
    "humidity": [PERCENTAGE, None, DEVICE_CLASS_HUMIDITY],
    "illumination": ["lm", None, DEVICE_CLASS_ILLUMINANCE],
    "lux": ["lx", None, DEVICE_CLASS_ILLUMINANCE],
    "pressure": ["hPa", None, DEVICE_CLASS_PRESSURE],
    "bed_activity": ["μm", None, None],
    "load_power": [POWER_WATT, None, DEVICE_CLASS_POWER],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Xiaomi devices."""
    entities = []
    gateway = hass.data[DOMAIN][GATEWAYS_KEY][config_entry.entry_id]
    for device in gateway.devices["sensor"]:
        if device["model"] == "sensor_ht":
            entities.append(
                XiaomiSensor(
                    device, "Temperature", "temperature", gateway, config_entry
                )
            )
            entities.append(
                XiaomiSensor(device, "Humidity", "humidity", gateway, config_entry)
            )
        elif device["model"] in ["weather", "weather.v1"]:
            entities.append(
                XiaomiSensor(
                    device, "Temperature", "temperature", gateway, config_entry
                )
            )
            entities.append(
                XiaomiSensor(device, "Humidity", "humidity", gateway, config_entry)
            )
            entities.append(
                XiaomiSensor(device, "Pressure", "pressure", gateway, config_entry)
            )
        elif device["model"] == "sensor_motion.aq2":
            entities.append(
                XiaomiSensor(device, "Illumination", "lux", gateway, config_entry)
            )
        elif device["model"] in ["gateway", "gateway.v3", "acpartner.v3"]:
            entities.append(
                XiaomiSensor(
                    device, "Illumination", "illumination", gateway, config_entry
                )
            )
        elif device["model"] in ["vibration"]:
            entities.append(
                XiaomiSensor(
                    device, "Bed Activity", "bed_activity", gateway, config_entry
                )
            )
            entities.append(
                XiaomiSensor(
                    device, "Tilt Angle", "final_tilt_angle", gateway, config_entry
                )
            )
            entities.append(
                XiaomiSensor(
                    device, "Coordination", "coordination", gateway, config_entry
                )
            )
        else:
            _LOGGER.warning("Unmapped Device Model")

    # Set up battery sensors
    for devices in gateway.devices.values():
        for device in devices:
            if device["model"] in BATTERY_MODELS:
                entities.append(
                    XiaomiBatterySensor(device, "Battery", gateway, config_entry)
                )
            if device["model"] in POWER_MODELS:
                entities.append(
                    XiaomiSensor(
                        device, "Load Power", "load_power", gateway, config_entry
                    )
                )
    async_add_entities(entities)


class XiaomiSensor(XiaomiDevice):
    """Representation of a XiaomiSensor."""

    def __init__(self, device, name, data_key, xiaomi_hub, config_entry):
        """Initialize the XiaomiSensor."""
        self._data_key = data_key
        super().__init__(device, name, xiaomi_hub, config_entry)

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


class XiaomiBatterySensor(XiaomiDevice):
    """Representation of a XiaomiSensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return PERCENTAGE

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        succeed = super().parse_voltage(data)
        if not succeed:
            return False
        battery_level = int(self._device_state_attributes.pop(ATTR_BATTERY_LEVEL))
        if battery_level <= 0 or battery_level > 100:
            return False
        self._state = battery_level
        return True

    def parse_voltage(self, data):
        """Parse battery level data sent by gateway."""
        return False  # Override parse_voltage to do nothing
