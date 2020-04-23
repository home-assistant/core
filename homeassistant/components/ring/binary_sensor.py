"""This component provides HA sensor support for Ring Door Bell/Chimes."""
from datetime import datetime
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback

from . import DOMAIN
from .entity import RingEntityMixin

_LOGGER = logging.getLogger(__name__)

# Sensor types: Name, category, device_class
SENSOR_TYPES = {
    "ding": ["Ding", ["doorbots", "authorized_doorbots"], "occupancy"],
    "motion": ["Motion", ["doorbots", "authorized_doorbots", "stickup_cams"], "motion"],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Ring binary sensors from a config entry."""
    ring = hass.data[DOMAIN][config_entry.entry_id]["api"]
    devices = hass.data[DOMAIN][config_entry.entry_id]["devices"]

    sensors = []

    for device_type in ("doorbots", "authorized_doorbots", "stickup_cams"):
        for sensor_type in SENSOR_TYPES:
            if device_type not in SENSOR_TYPES[sensor_type][1]:
                continue

            for device in devices[device_type]:
                sensors.append(
                    RingBinarySensor(config_entry.entry_id, ring, device, sensor_type)
                )

    async_add_entities(sensors)


class RingBinarySensor(RingEntityMixin, BinarySensorEntity):
    """A binary sensor implementation for Ring device."""

    _active_alert = None

    def __init__(self, config_entry_id, ring, device, sensor_type):
        """Initialize a sensor for Ring device."""
        super().__init__(config_entry_id, device)
        self._ring = ring
        self._sensor_type = sensor_type
        self._name = "{} {}".format(self._device.name, SENSOR_TYPES.get(sensor_type)[0])
        self._device_class = SENSOR_TYPES.get(sensor_type)[2]
        self._state = None
        self._unique_id = f"{device.id}-{sensor_type}"
        self._update_alert()

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()
        self.ring_objects["dings_data"].async_add_listener(self._dings_update_callback)
        self._dings_update_callback()

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        await super().async_will_remove_from_hass()
        self.ring_objects["dings_data"].async_remove_listener(
            self._dings_update_callback
        )

    @callback
    def _dings_update_callback(self):
        """Call update method."""
        self._update_alert()
        self.async_write_ha_state()

    @callback
    def _update_alert(self):
        """Update active alert."""
        self._active_alert = next(
            (
                alert
                for alert in self._ring.active_alerts()
                if alert["kind"] == self._sensor_type
                and alert["doorbot_id"] == self._device.id
            ),
            None,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._active_alert is not None

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
        attrs = super().device_state_attributes

        if self._active_alert is None:
            return attrs

        attrs["state"] = self._active_alert["state"]
        attrs["expires_at"] = datetime.fromtimestamp(
            self._active_alert.get("now") + self._active_alert.get("expires_in")
        ).isoformat()

        return attrs
