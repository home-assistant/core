"""
Support for UPnP Sensors (IGD).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.upnp/
"""
import logging

from homeassistant.components.upnp import DATA_UPNP, UNITS, CIC_SERVICE
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['upnp']

BYTES_RECEIVED = 1
BYTES_SENT = 2
PACKETS_RECEIVED = 3
PACKETS_SENT = 4

# sensor_type: [friendly_name, convert_unit, icon]
SENSOR_TYPES = {
    BYTES_RECEIVED: ['received bytes', True, 'mdi:server-network'],
    BYTES_SENT: ['sent bytes', True, 'mdi:server-network'],
    PACKETS_RECEIVED: ['packets received', False, 'mdi:server-network'],
    PACKETS_SENT: ['packets sent', False, 'mdi:server-network'],
}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the IGD sensors."""
    if discovery_info is None:
        return

    device = hass.data[DATA_UPNP]
    service = device.find_first_service(CIC_SERVICE)
    unit = discovery_info['unit']
    async_add_entities([
        IGDSensor(service, t, unit if SENSOR_TYPES[t][1] else '#')
        for t in SENSOR_TYPES], True)


class IGDSensor(Entity):
    """Representation of a UPnP IGD sensor."""

    def __init__(self, service, sensor_type, unit=None):
        """Initialize the IGD sensor."""
        self._service = service
        self.type = sensor_type
        self.unit = unit
        self.unit_factor = UNITS[unit] if unit in UNITS else 1
        self._name = 'IGD {}'.format(SENSOR_TYPES[sensor_type][0])
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._state:
            return format(float(self._state) / self.unit_factor, '.1f')
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.unit

    async def async_update(self):
        """Get the latest information from the IGD."""
        if self.type == BYTES_RECEIVED:
            self._state = await self._service.get_total_bytes_received()
        elif self.type == BYTES_SENT:
            self._state = await self._service.get_total_bytes_sent()
        elif self.type == PACKETS_RECEIVED:
            self._state = await self._service.get_total_packets_received()
        elif self.type == PACKETS_SENT:
            self._state = await self._service.get_total_packets_sent()
