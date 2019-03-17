"""
Support for Qwikswitch Binary Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.qwikswitch/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.qwikswitch import QSEntity, DOMAIN as QWIKSWITCH
from homeassistant.core import callback

DEPENDENCIES = [QWIKSWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, _, add_entities, discovery_info=None):
    """Add binary sensor from the main Qwikswitch component."""
    if discovery_info is None:
        return

    qsusb = hass.data[QWIKSWITCH]
    _LOGGER.debug("Setup qwikswitch.binary_sensor %s, %s",
                  qsusb, discovery_info)
    devs = [QSBinarySensor(sensor) for sensor in discovery_info[QWIKSWITCH]]
    add_entities(devs)


class QSBinarySensor(QSEntity, BinarySensorDevice):
    """Sensor based on a Qwikswitch relay/dimmer module."""

    _val = False

    def __init__(self, sensor):
        """Initialize the sensor."""
        from pyqwikswitch import SENSORS

        super().__init__(sensor['id'], sensor['name'])
        self.channel = sensor['channel']
        sensor_type = sensor['type']

        self._decode, _ = SENSORS[sensor_type]
        self._invert = not sensor.get('invert', False)
        self._class = sensor.get('class', 'door')

    @callback
    def update_packet(self, packet):
        """Receive update packet from QSUSB."""
        val = self._decode(packet, channel=self.channel)
        _LOGGER.debug("Update %s (%s:%s) decoded as %s: %s",
                      self.entity_id, self.qsid, self.channel, val, packet)
        if val is not None:
            self._val = bool(val)
            self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Check if device is on (non-zero)."""
        return self._val == self._invert

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return "qs{}:{}".format(self.qsid, self.channel)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._class
