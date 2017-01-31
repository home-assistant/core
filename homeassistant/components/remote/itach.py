"""
Control an itach ip2ir gateway using libitachip2ir.

Requires a command file with Philips Pronto learned hex formats.

Example command file:

OFF
0000 006d 0022 0002 0157 00ac 0015 0016 0015 0016 0015 0041 0015

ON
0000 006d 0022 0002 0157 00ac 0015 0016 0015 0016 0041 0015 0015

Example configuration.yaml section:
remote living_room:
  - platform: itach
    name: Living Room
    mac: 000C1E023FDC
    ip: itach023fdc
    port: 4998
    devices:
      - { name: TV,  connaddr: 2, file: Samsung_TV.txt }
      - { name: DVD, connaddr: 3, file: LG_BR.txt }
"""

import logging

from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.components.remote as remote
from homeassistant.components.remote import ATTR_COMMAND

REQUIREMENTS = ['pyitachip2ir==0.0.5']

_LOGGER = logging.getLogger(__name__)

CONF_MAC = 'mac'
CONF_IP = 'ip'
CONF_PORT = 'port'
CONF_FILE = 'file'
CONF_DEVICES = 'devices'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ITach connection and devices."""
    import pyitachip2ir
    itachip2ir = pyitachip2ir.ITachIP2IR(
        config.get(CONF_MAC), config.get(CONF_IP), int(config.get(CONF_PORT)))
    devices = []
    for data in config.get(CONF_DEVICES):
        name = data['name']
        modaddr = int(data.get('modaddr', 1))
        connaddr = int(data.get('connaddr', 1))
        cmddata = open(
            hass.config.config_dir + "/" + data.get('file'), "r").read()
        itachip2ir.addDevice(name, modaddr, connaddr, cmddata)
        devices.append(ITachIP2IRRemote(itachip2ir, name))
    add_devices(devices, True)


class ITachIP2IRRemote(remote.RemoteDevice):
    """Device that sends commands to an ITachIP2IR device."""

    def __init__(self, itachip2ir, name):
        """Initialize device."""
        self.itachip2ir = itachip2ir
        self._power = False
        self._name = name or DEVICE_DEFAULT_NAME

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._power

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._power = True
        self.itachip2ir.send(self._name, "ON", 1)
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn the device off."""
        self._power = False
        self.itachip2ir.send(self._name, "OFF", 1)
        self.schedule_update_ha_state()

    def send_command(self, **kwargs):
        """Send a command to one device."""
        self.itachip2ir.send(self._name, kwargs[ATTR_COMMAND], 1)

    def update(self):
        """Update the device."""
        self.itachip2ir.update()
