"""
Support for Qwikswitch Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.qwikswitch/
"""
import logging

from homeassistant.components.qwikswitch import DOMAIN as QWIKSWITCH, QSEntity
from homeassistant.core import callback

DEPENDENCIES = [QWIKSWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, _, add_devices, discovery_info=None):
    """Add sensor from the main Qwikswitch component."""
    if discovery_info is None:
        return

    qsusb = hass.data[QWIKSWITCH]
    _LOGGER.debug("Setup qwikswitch.sensor %s, %s", qsusb, discovery_info)
    devs = [QSSensor(sensor) for sensor in discovery_info[QWIKSWITCH]]
    add_devices(devs)


class QSSensor(QSEntity):
    """Sensor based on a Qwikswitch relay/dimmer module."""

    _val = None

    def __init__(self, sensor):
        """Initialize the sensor."""
        from pyqwikswitch import SENSORS

        super().__init__(sensor['id'], sensor['name'])
        self.channel = sensor['channel']
        sensor_type = sensor['type']

        self._decode, self.unit = SENSORS[sensor_type]
        if isinstance(self.unit, type):
            self.unit = "{}:{}".format(sensor_type, self.channel)

    @callback
    def update_packet(self, packet):
        """Receive update packet from QSUSB."""
        val = self._decode(packet, channel=self.channel)
        _LOGGER.debug("Update %s (%s:%s) decoded as %s: %s",
                      self.entity_id, self.qsid, self.channel, val, packet)
        if val is not None:
            self._val = val
            self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the value of the sensor."""
        return str(self._val)

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return "qs{}:{}".format(self.qsid, self.channel)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self.unit
