"""
Support for UPnP Sensors (IGD).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.upnp/
"""
import logging

from homeassistant.components.upnp import DATA_UPNP, UNITS
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# sensor_type: [friendly_name, convert_unit, icon]
SENSOR_TYPES = {
    'byte_received': ['received bytes', True, 'mdi:server-network'],
    'byte_sent': ['sent bytes', True, 'mdi:server-network'],
    'packets_in': ['packets received', False, 'mdi:server-network'],
    'packets_out': ['packets sent', False, 'mdi:server-network'],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the IGD sensors."""
    upnp = hass.data[DATA_UPNP]
    unit = discovery_info['unit']
    add_devices([
        IGDSensor(upnp, t, unit if SENSOR_TYPES[t][1] else None)
        for t in SENSOR_TYPES], True)


class IGDSensor(Entity):
    """Representation of a UPnP IGD sensor."""

    def __init__(self, upnp, sensor_type, unit=""):
        """Initialize the IGD sensor."""
        self._upnp = upnp
        self.type = sensor_type
        self.unit = unit
        self.unit_factor = UNITS[unit] if unit is not None else 1
        self._name = 'IGD {}'.format(SENSOR_TYPES[sensor_type][0])
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._state is None:
            return None
        return format(self._state / self.unit_factor, '.1f')

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.unit

    def update(self):
        """Get the latest information from the IGD."""
        if self.type == "byte_received":
            self._state = self._upnp.totalbytereceived()
        elif self.type == "byte_sent":
            self._state = self._upnp.totalbytesent()
        elif self.type == "packets_in":
            self._state = self._upnp.totalpacketreceived()
        elif self.type == "packets_out":
            self._state = self._upnp.totalpacketsent()
