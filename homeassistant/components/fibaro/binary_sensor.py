"""Support for Fibaro binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_WINDOW,
    DOMAIN,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ICON

from . import FIBARO_DEVICES, FibaroDevice

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "com.fibaro.floodSensor": ["Flood", "mdi:water", "flood"],
    "com.fibaro.motionSensor": ["Motion", "mdi:run", DEVICE_CLASS_MOTION],
    "com.fibaro.doorSensor": ["Door", "mdi:window-open", DEVICE_CLASS_DOOR],
    "com.fibaro.windowSensor": ["Window", "mdi:window-open", DEVICE_CLASS_WINDOW],
    "com.fibaro.smokeSensor": ["Smoke", "mdi:smoking", DEVICE_CLASS_SMOKE],
    "com.fibaro.FGMS001": ["Motion", "mdi:run", DEVICE_CLASS_MOTION],
    "com.fibaro.heatDetector": ["Heat", "mdi:fire", "heat"],
}


# Ais dom
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Fibaro controller devices."""
    async_add_entities(
        [
            FibaroBinarySensor(device)
            for device in hass.data[FIBARO_DEVICES]["binary_sensor"]
        ],
        True,
    )


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Fibaro controller devices."""
    if discovery_info is None:
        return

    add_entities(
        [
            FibaroBinarySensor(device)
            for device in hass.data[FIBARO_DEVICES]["binary_sensor"]
        ],
        True,
    )


class FibaroBinarySensor(FibaroDevice, BinarySensorEntity):
    """Representation of a Fibaro Binary Sensor."""

    def __init__(self, fibaro_device):
        """Initialize the binary_sensor."""
        self._state = None
        super().__init__(fibaro_device)
        self.entity_id = f"{DOMAIN}.{self.ha_id}"
        stype = None
        devconf = fibaro_device.device_config
        if fibaro_device.type in SENSOR_TYPES:
            stype = fibaro_device.type
        elif fibaro_device.baseType in SENSOR_TYPES:
            stype = fibaro_device.baseType
        if stype:
            self._device_class = SENSOR_TYPES[stype][2]
            self._icon = SENSOR_TYPES[stype][1]
        else:
            self._device_class = None
            self._icon = None
        # device_config overrides:
        self._device_class = devconf.get(CONF_DEVICE_CLASS, self._device_class)
        self._icon = devconf.get(CONF_ICON, self._icon)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and update the state."""
        self._state = self.current_binary_state
