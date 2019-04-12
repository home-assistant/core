"""Support for ZoneMinder binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorDevice

from . import DOMAIN as ZONEMINDER_DOMAIN

DEPENDENCIES = ['zoneminder']


async def async_setup_platform(
        hass, config, add_entities, discovery_info=None):
    """Set up the ZoneMinder binary sensor platform."""
    sensors = []
    for host_name, zm_client in hass.data[ZONEMINDER_DOMAIN].items():
        sensors.append(ZMAvailabilitySensor(host_name, zm_client))
    add_entities(sensors)
    return True


class ZMAvailabilitySensor(BinarySensorDevice):
    """Representation of the availability of ZoneMinder as a binary sensor."""

    def __init__(self, host_name, client):
        """Initialize availability sensor."""
        self._state = None
        self._name = host_name
        self._client = client

    @property
    def name(self):
        """Return the name of this binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'connectivity'

    def update(self):
        """Update the state of this sensor (availability of ZoneMinder)."""
        self._state = self._client.is_available
