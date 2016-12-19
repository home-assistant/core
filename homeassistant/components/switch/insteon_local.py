"""
Support for Insteon switch devices via local hub support

Based on the insteonlocal library
https://github.com/phareous/insteonlocal

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.insteon_local/

--
Example platform config
--

insteon_local:
  host: YOUR HUB IP
  username: YOUR HUB USERNAME
  password: YOUR HUB PASSWORD
  timeout: 10
  port: 25105

--
Example platform config
--

switch:
   - platform: insteon_local
     switches:
       dining_room:
          device_id: 30DA8A
          name: Dining Room
       living_room:
       device_id: 30D927
       name: Living Room

"""
import logging
from time import sleep
from datetime import timedelta
from homeassistant.components.switch import SwitchDevice
import homeassistant.util as util

DEPENDENCIES = ['insteon_local']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

DOMAIN = "switch"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Insteon local switch platform."""
    insteonhub = hass.data['insteon_local']
    devs = []
    if len(config) > 0:
        items = config['switches'].items()

        # todo: use getLinked instead
        for switch in items:
            device = insteonhub.switch(switch[1]['device_id'])
            device.beep()
            devs.append(InsteonLocalSwitchDevice(device, switch[1]['name']))
        add_devices(devs)


class InsteonLocalSwitchDevice(SwitchDevice):
    """An abstract Class for an Insteon node."""

    def __init__(self, node, name):
        """Initialize the device."""
        self.node = node
        self.node.deviceName = name
        self._state = False

    @property
    def name(self):
        """Return the the name of the node."""
        return self.node.deviceName

    @property
    def unique_id(self):
        """Return the ID of this insteon node."""
        return self.node.deviceId

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Update state of the sensor."""
        devid = self.node.deviceId.upper()
        self.node.hub.directCommand(devid, '19', '00')
        resp = self.node.hub.getBufferStatus(devid)
        attempts = 1
        while 'cmd2' not in resp and attempts < 9:
            if attempts % 3 == 0:
                self.node.hub.directCommand(devid, '19', '00')
            else:
                sleep(2)
            resp = self.node.hub.getBufferStatus(devid)
            attempts += 1

        if 'cmd2' in resp:
            _LOGGER.info("cmd2 value = " + resp['cmd2'])
            self._state = int(resp['cmd2'], 16) > 0

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.node.on()
        self._state = True

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.node.off()
        self._state = False
