"""Support for Android IP Webcam binary sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    BinarySensorEntity,
)

from . import CONF_HOST, CONF_NAME, DATA_IP_WEBCAM, KEY_MAP, AndroidIPCamEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the IP Webcam binary sensors."""
    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    name = discovery_info[CONF_NAME]
    ipcam = hass.data[DATA_IP_WEBCAM][host]

    async_add_entities([IPWebcamBinarySensor(name, host, ipcam, "motion_active")], True)


class IPWebcamBinarySensor(AndroidIPCamEntity, BinarySensorEntity):
    """Representation of an IP Webcam binary sensor."""

    _attr_device_class = DEVICE_CLASS_MOTION

    def __init__(self, name, host, ipcam, sensor):
        """Initialize the binary sensor."""
        super().__init__(host, ipcam)

        self._sensor = sensor
        self._mapped_name = KEY_MAP.get(self._sensor, self._sensor)
        self._attr_name = f"{name} {self._mapped_name}"
        self._state = None
        self._unit = None

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    async def async_update(self):
        """Retrieve latest state."""
        state, _ = self._ipcam.export_sensor(self._sensor)
        self._state = state == 1.0
