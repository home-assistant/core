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
    if discovery_info is None:
        return

    qsusb = hass.data[QWIKSWITCH]
    _LOGGER.debug("Setup qwikswitch.sensor %s, %s", qsusb, discovery_info)
    devs = [QSSensor(name, qsid)
            for name, qsid in discovery_info[QWIKSWITCH].items()]
    add_devices(devs)


class QSSensor(Entity):
    """Sensor based on a Qwikswitch relay/dimmer module."""

    _val = None

    def __init__(self, sensor_name, sensor_id):
        """Initialize the sensor."""
        self._name = sensor_name
        dat = sensor_id.split(':')
        self.qsid = dat[0]
        self._params = {}
        if dat[1]:
            self._params['channel'] = int(dat[1])
        self.sensor = dat[2]
        self._decode, self.unit = SENSORS[self.sensor]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    def update_packet(self, packet):
        """Receive update packet from QSUSB."""
        val = self._decode(packet.get('data'), **self._params)
        _LOGGER.debug("Update %s (%s) decoded as %s: %s: %s",
                      self.entity_id, self.qsid, val, self._params, packet)
        if val:
            self._val = val
            self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the value of the sensor."""
        return str(self._val)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self.unit

    @property
    def poll(self):
        """QS sensors gets packets in update_packet."""
        return False

    async def async_added_to_hass(self):
        """Listen for updates from QSUSb via dispatcher."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            self.qsid, self.update_packet)


# byte 0:
#     4e = imod
#     46 = Door sensor
# byte 1: firmware
# byte 2:  bit values
#     00/64: Door open / Close
#     17/xx: All open / Channels 1-4 at 0004 0321
# byte 3: last change (imod)


def decode_qwikcord_ctavg(val):
    """Extract the qwikcord current measurements from val (CTavg, _)."""
    if len(val) != 16:
        return None
    return int(val[6:12], 16)


def decode_qwikcord_ctsum(val):
    """Extract the qwikcord current measurements from val (_, CTsum)."""
    if len(val) != 16:
        return None
    return int(val[12:], 16)


def decode_door(val):
    """Decode a door sensor."""
    if len(val) == 6 and val.startswith('46'):
        return val[-1] == '0'
    return None


def decode_imod(val, channel=0):
    """Decode an 4 channel imod."""
    if len(val) == 8 and val.startswith('4e') and channel < 4:
        _map = ((5, 1), (5, 2), (5, 4), (4, 1))[channel]
        return (int(val[_map[0]], 16) & _map[1]) == 0
    return None


SENSORS = {
    'imod': (decode_imod, None),
    'door': (decode_door, None),
    'qwikcord_ctavg': (decode_qwikcord_ctavg, 'A/s'),
    'qwikcord_ctsum': (decode_qwikcord_ctsum, 'A/s'),
}
