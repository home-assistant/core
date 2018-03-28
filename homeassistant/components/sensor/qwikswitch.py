"""
Support for Qwikswitch Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.qwikswitch/
"""
import logging

from homeassistant.components.qwikswitch import DOMAIN as QWIKSWITCH
from homeassistant.helpers.entity import Entity

DEPENDENCIES = [QWIKSWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, _, add_devices, discovery_info=None):
    """Add lights from the main Qwikswitch component."""
    qsusb = hass.data[QWIKSWITCH]
    _LOGGER.info("Setup qwikswitch.sensor %s, %s", qsusb, discovery_info)
    devs = [QSSensor(name, id)
            for name, id in discovery_info[QWIKSWITCH].items()]

    add_devices(devs)

    for dev in devs:
        hass.helpers.dispatcher.async_dispatcher_connect(
            dev.qsid, dev.update_packet)  # Part of Entity/ToggleEntity


class QSSensor(Entity):
    """Sensor based on a Qwikswitch relay/dimmer module."""

    _val = {}

    def __init__(self, sensor_name, sensor_id):
        """Initialize the sensor."""
        self._name = sensor_name
        self.qsid = sensor_id

    def update_packet(self, packet):
        """Receive update packet from QSUSB."""
        self._val = packet

    @property
    def state(self):
        """Return the value of the sensor."""
        return self._val.get('data', 0)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._val

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return None

    @property
    def poll(self):
        """QS sensors gets packets in update_packet."""
        return False
