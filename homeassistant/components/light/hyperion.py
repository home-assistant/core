"""
Support for Hyperion remotes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.hyperion/
"""
import json
import logging
import socket

from homeassistant.components.light import ATTR_RGB_COLOR, Light
from homeassistant.const import CONF_HOST

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = []


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup a Hyperion server remote."""
    host = config.get(CONF_HOST, None)
    port = config.get("port", 19444)
    device = Hyperion(config.get('name', host), host, port)
    if device.setup():
        add_devices_callback([device])
        return True
    else:
        return False


class Hyperion(Light):
    """Representation of a Hyperion remote."""

    def __init__(self, name, host, port):
        """Initialize the light."""
        self._host = host
        self._port = port
        self._name = name
        self._is_available = True
        self._rgb_color = [255, 255, 255]

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
        """Return true if the device is online."""
        return self._is_available

    def turn_on(self, **kwargs):
        """Turn the lights on."""
        if self._is_available:
            if ATTR_RGB_COLOR in kwargs:
                self._rgb_color = kwargs[ATTR_RGB_COLOR]

            self.json_request({"command": "color", "priority": 128,
                               "color": self._rgb_color})

    def turn_off(self, **kwargs):
        """Disconnect the remote."""
        self.json_request({"command": "clearall"})

    def update(self):
        """Ping the remote."""
        # just see if the remote port is open
        self._is_available = self.json_request()

    def setup(self):
        """Get the hostname of the remote."""
        response = self.json_request({"command": "serverinfo"})
        if response:
            if self._name == self._host:
                self._name = response["info"]["hostname"]
            return True

        return False

    def json_request(self, request=None, wait_for_response=False):
        """Communicate with the JSON server."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        try:
            sock.connect((self._host, self._port))
        except OSError:
            sock.close()
            return False

        if not request:
            # No communication needed, simple presence detection returns True
            sock.close()
            return True

        sock.send(bytearray(json.dumps(request) + "\n", "utf-8"))
        try:
            buf = sock.recv(4096)
        except socket.timeout:
            # Something is wrong, assume it's offline
            sock.close()
            return False

        # Read until a newline or timeout
        buffering = True
        while buffering:
            if "\n" in str(buf, "utf-8"):
                response = str(buf, "utf-8").split("\n")[0]
                buffering = False
            else:
                try:
                    more = sock.recv(4096)
                except socket.timeout:
                    more = None
                if not more:
                    buffering = False
                    response = str(buf, "utf-8")
                else:
                    buf += more

        sock.close()
        return json.loads(response)
