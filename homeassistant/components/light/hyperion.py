"""
homeassistant.components.light.hyperion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Hyperion remotes.

Configuration:

To connect to [a Hyperion server](https://github.com/tvdzwan/hyperion) you
will need to add something like the following to your configuration.yaml file:

light:
    platform: hyperion
    host: 192.168.1.98
    port: 19444

The JSON server port is 19444 by default.
"""
import logging
import socket
import json

from homeassistant.const import CONF_HOST
from homeassistant.components.light import (Light, ATTR_XY_COLOR,
                                            ATTR_BRIGHTNESS)
from homeassistant.util.color import color_RGB_to_xy, \
                                     color_xy_brightness_to_RGB

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = []


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Sets up a Hyperion server remote """
    host = config.get(CONF_HOST, None)
    port = config.get("port", 19444)
    add_devices_callback([Hyperion(host, port)])


class Hyperion(Light):
    """ Represents a Hyperion remote """

    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._name = "unknown"
        self._is_available = False
        self._xy_color = color_RGB_to_xy(0, 0, 0)
        self._brightness = 255

    @property
    def name(self):
        """ Get the hostname of the server. """
        return self._name

    @property
    def color_xy(self):
        """ XY color value. """
        return self._xy_color

    @property
    def brightness(self):
        """ Brightness. """
        return self._brightness

    @property
    def is_on(self):
        """ True if device is on. """
        self.check_remote()
        return self._is_available

    def turn_on(self, **kwargs):
        """ Turn the lights on. """
        if self._is_available:
            if ATTR_XY_COLOR in kwargs:
                self._xy_color = kwargs[ATTR_XY_COLOR]
            if ATTR_BRIGHTNESS in kwargs:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
            self.update_remote()

    def turn_off(self, **kwargs):
        """ Disconnect the remote. """
        self.json_request({"command": "clearall"})

    def check_remote(self):
        """ Ping the remote and gets the hostname. """
        response = self.json_request({"command": "serverinfo"})
        if response:
            self._name = response["info"]["hostname"]

    def update_remote(self):
        """ Set the remote's lights. """
        rgb = color_xy_brightness_to_RGB(self._xy_color[0], self._xy_color[1],
                                         self._brightness)
        rgb = [int(c) for c in rgb]
        self.json_request(
            {"command": "color", "priority": 128, "color": rgb})

    def json_request(self, request, wait_for_response=False):
        """ Communicate with the json server. """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self._host, self._port))
        except OSError:
            self._is_available = False
            return None

        sock.send(bytearray(json.dumps(request) + "\n", "utf-8"))

        try:
            buf = sock.recv(4096)
        except socket.timeout:
            return None

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

        j = json.loads(response)
        self._is_available = True
        return j
