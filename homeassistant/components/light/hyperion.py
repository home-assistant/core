"""
Support for Hyperion remotes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.hyperion/
"""
import json
import logging
import socket

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_RGB_COLOR, SUPPORT_RGB_COLOR, Light, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_COLOR = 'default_color'

DEFAULT_COLOR = [255, 255, 255]
DEFAULT_NAME = 'Hyperion'
DEFAULT_PORT = 19444

SUPPORT_HYPERION = SUPPORT_RGB_COLOR

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_DEFAULT_COLOR, default=DEFAULT_COLOR): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a Hyperion server remote."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    default_color = config.get(CONF_DEFAULT_COLOR)

    device = Hyperion(config.get(CONF_NAME), host, port, default_color)

    if device.setup():
        add_devices([device])
        return True
    return False


class Hyperion(Light):
    """Representation of a Hyperion remote."""

    def __init__(self, name, host, port, default_color):
        """Initialize the light."""
        self._host = host
        self._port = port
        self._name = name
        self._default_color = default_color
        self._rgb_color = [0, 0, 0]

    @property
    def name(self):
        """Return the hostname of the server."""
        return self._name

    @property
    def rgb_color(self):
        """Return last RGB color value set."""
        return self._rgb_color

    @property
    def is_on(self):
        """Return true if not black."""
        return self._rgb_color != [0, 0, 0]

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_HYPERION

    def turn_on(self, **kwargs):
        """Turn the lights on."""
        if ATTR_RGB_COLOR in kwargs:
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
        else:
            self._rgb_color = self._default_color

        self.json_request(
            {'command': 'color', 'priority': 128, 'color': self._rgb_color})

    def turn_off(self, **kwargs):
        """Disconnect all remotes."""
        self.json_request({'command': 'clearall'})
        self._rgb_color = [0, 0, 0]

    def update(self):
        """Get the remote's active color."""
        response = self.json_request({'command': 'serverinfo'})
        if response:
            # workaround for outdated Hyperion
            if 'activeLedColor' not in response['info']:
                self._rgb_color = self._default_color
                return

            if response['info']['activeLedColor'] == []:
                self._rgb_color = [0, 0, 0]
            else:
                self._rgb_color =\
                    response['info']['activeLedColor'][0]['RGB Value']

    def setup(self):
        """Get the hostname of the remote."""
        response = self.json_request({'command': 'serverinfo'})
        if response:
            self._name = response['info']['hostname']
            return True
        return False

    def json_request(self, request, wait_for_response=False):
        """Communicate with the JSON server."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        try:
            sock.connect((self._host, self._port))
        except OSError:
            sock.close()
            return False

        sock.send(bytearray(json.dumps(request) + '\n', 'utf-8'))
        try:
            buf = sock.recv(4096)
        except socket.timeout:
            # Something is wrong, assume it's offline
            sock.close()
            return False

        # Read until a newline or timeout
        buffering = True
        while buffering:
            if '\n' in str(buf, 'utf-8'):
                response = str(buf, 'utf-8').split('\n')[0]
                buffering = False
            else:
                try:
                    more = sock.recv(4096)
                except socket.timeout:
                    more = None
                if not more:
                    buffering = False
                    response = str(buf, 'utf-8')
                else:
                    buf += more

        sock.close()
        return json.loads(response)
