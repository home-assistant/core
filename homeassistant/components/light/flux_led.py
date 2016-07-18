"""
Support for Flux lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.flux_led/
"""

import logging
import socket
import voluptuous as vol

from homeassistant.components.light import Light
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['https://github.com/Danielhiversen/flux_led/archive/0.3.zip'
                '#flux_led==0.3']

_LOGGER = logging.getLogger(__name__)
DOMAIN = "flux_led"
ATTR_NAME = 'name'

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_NAME): cv.string,
})

PLATFORM_SCHEMA = vol.Schema({
    vol.Required('platform'): DOMAIN,
    vol.Optional('devices', default={}): {cv.string: DEVICE_SCHEMA},
    vol.Optional('automatic_add', default=False):  cv.boolean,
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the Flux lights."""
    import flux_led
    lights = []
    light_ips = []
    for ipaddr, device_config in config["devices"].items():
        device = {}
        device['id'] = device_config[ATTR_NAME]
        device['ipaddr'] = ipaddr
        light = FluxLight(device)
        if light.is_valid:
            lights.append(light)
            light_ips.append(ipaddr)

    if not config['automatic_add']:
        add_devices_callback(lights)
        return

    # Find the bulbs on the LAN
    scanner = flux_led.BulbScanner()
    scanner.scan(timeout=20)
    for device in scanner.getBulbInfo():
        light = FluxLight(device)
        ipaddr = device['ipaddr']
        if light.is_valid and ipaddr not in light_ips:
            lights.append(light)
            light_ips.append(ipaddr)

    add_devices_callback(lights)


class FluxLight(Light):
    """Representation of a Flux light."""

    # pylint: disable=too-many-arguments
    def __init__(self, device):
        """Initialize the light."""
        import flux_led

        self._name = device['id']
        self._ipaddr = device['ipaddr']
        self.is_valid = True
        self._bulb = None
        try:
            self._bulb = flux_led.WifiLedBulb(self._ipaddr)
        except socket.error:
            self.is_valid = False
            _LOGGER.error("Failed to connect to bulb %s, %s",
                          self._ipaddr, self._name)

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return "{}.{}".format(
            self.__class__, self._ipaddr)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._bulb.isOn()

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        self._bulb.turnOn()

    def turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        self._bulb.turnOff()

    def update(self):
        """Synchronize state with bulb."""
        self._bulb.refreshState()
