"""This component provides HA sensor support for Ring Door Bell/Chimes."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import ATTR_ATTRIBUTION

from . import ATTRIBUTION, DATA_RING_DOORBELLS, DATA_RING_STICKUP_CAMS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

# Sensor types: Name, category, device_class
SENSOR_TYPES = {
    "ding": ["Ding", ["doorbell"], "occupancy"],
    "motion": ["Motion", ["doorbell", "stickup_cams"], "motion"],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Ring binary sensors from a config entry."""
    ring_doorbells = hass.data[DATA_RING_DOORBELLS]
    ring_stickup_cams = hass.data[DATA_RING_STICKUP_CAMS]

    sensors = []
    for device in ring_doorbells:  # ring.doorbells is doing I/O
        for sensor_type in SENSOR_TYPES:
            if "doorbell" in SENSOR_TYPES[sensor_type][1]:
                sensors.append(RingBinarySensor(hass, device, sensor_type))

    for device in ring_stickup_cams:  # ring.stickup_cams is doing I/O
        for sensor_type in SENSOR_TYPES:
            if "stickup_cams" in SENSOR_TYPES[sensor_type][1]:
                sensors.append(RingBinarySensor(hass, device, sensor_type))

    async_add_entities(sensors, True)


class RingBinarySensor(BinarySensorDevice):
    """A binary sensor implementation for Ring device."""

    def __init__(self, hass, data, sensor_type):
        """Initialize a sensor for Ring device."""
        super().__init__()
        self._sensor_type = sensor_type
        self._data = data
        self._name = "{0} {1}".format(
            self._data.name, SENSOR_TYPES.get(self._sensor_type)[0]
        )
        self._device_class = SENSOR_TYPES.get(self._sensor_type)[2]
        self._state = None
        self._unique_id = f"{self._data.id}-{self._sensor_type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION

        attrs["device_id"] = self._data.id
        attrs["firmware"] = self._data.firmware
        attrs["timezone"] = self._data.timezone

        if self._data.alert and self._data.alert_expires_at:
            attrs["expires_at"] = self._data.alert_expires_at
            attrs["state"] = self._data.alert.get("state")

        return attrs

    def update(self):
        """Get the latest data and updates the state."""
        self._data.check_alerts()

        if self._data.alert:
            if self._sensor_type == self._data.alert.get(
                "kind"
            ) and self._data.account_id == self._data.alert.get("doorbot_id"):
                self._state = True
        else:
            self._state = False
