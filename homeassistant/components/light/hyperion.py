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
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, ATTR_EFFECT, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, SUPPORT_EFFECT, Light, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_NAME)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_COLOR = 'default_color'
CONF_PRIORITY = 'priority'
CONF_HDMI_PRIORITY = 'hdmi_priority'
CONF_EFFECT_LIST = 'effect_list'

DEFAULT_COLOR = [255, 255, 255]
DEFAULT_NAME = 'Hyperion'
DEFAULT_PORT = 19444
DEFAULT_PRIORITY = 128
DEFAULT_HDMI_PRIORITY = 880
DEFAULT_EFFECT_LIST = ['HDMI', 'Cinema brighten lights', 'Cinema dim lights',
                       'Knight rider', 'Blue mood blobs', 'Cold mood blobs',
                       'Full color mood blobs', 'Green mood blobs',
                       'Red mood blobs', 'Warm mood blobs',
                       'Police Lights Single', 'Police Lights Solid',
                       'Rainbow mood', 'Rainbow swirl fast',
                       'Rainbow swirl', 'Random', 'Running dots',
                       'System Shutdown', 'Snake', 'Sparks Color', 'Sparks',
                       'Strobe blue', 'Strobe Raspbmc', 'Strobe white',
                       'Color traces', 'UDP multicast listener',
                       'UDP listener', 'X-Mas']

SUPPORT_HYPERION = (SUPPORT_COLOR | SUPPORT_BRIGHTNESS | SUPPORT_EFFECT)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_DEFAULT_COLOR, default=DEFAULT_COLOR):
    vol.All(list, vol.Length(min=3, max=3),
            [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PRIORITY, default=DEFAULT_PRIORITY): cv.positive_int,
    vol.Optional(CONF_HDMI_PRIORITY,
                 default=DEFAULT_HDMI_PRIORITY): cv.positive_int,
    vol.Optional(CONF_EFFECT_LIST,
                 default=DEFAULT_EFFECT_LIST): vol.All(cv.ensure_list,
                                                       [cv.string]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a Hyperion server remote."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    priority = config.get(CONF_PRIORITY)
    hdmi_priority = config.get(CONF_HDMI_PRIORITY)
    default_color = config.get(CONF_DEFAULT_COLOR)
    effect_list = config.get(CONF_EFFECT_LIST)

    device = Hyperion(config.get(CONF_NAME), host, port, priority,
                      default_color, hdmi_priority, effect_list)

    if device.setup():
        add_devices([device])
        return True
    return False


class Hyperion(Light):
    """Representation of a Hyperion remote."""

    def __init__(self, name, host, port, priority, default_color,
                 hdmi_priority, effect_list):
        """Initialize the light."""
        self._host = host
        self._port = port
        self._name = name
        self._priority = priority
        self._hdmi_priority = hdmi_priority
        self._default_color = default_color
        self._rgb_color = [0, 0, 0]
        self._rgb_mem = [0, 0, 0]
        self._brightness = 255
        self._icon = 'mdi:lightbulb'
        self._effect_list = effect_list
        self._effect = None
        self._skip_update = False

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return last color value set."""
        return color_util.color_RGB_to_hs(*self._rgb_color)

    @property
    def is_on(self):
        """Return true if not black."""
        return self._rgb_color != [0, 0, 0]

    @property
    def icon(self):
        """Return state specific icon."""
        return self._icon

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._effect_list

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_HYPERION

    def turn_on(self, **kwargs):
        """Turn the lights on."""
        if ATTR_HS_COLOR in kwargs:
            rgb_color = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
        elif self._rgb_mem == [0, 0, 0]:
            rgb_color = self._default_color
        else:
            rgb_color = self._rgb_mem

        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)

        if ATTR_EFFECT in kwargs:
            self._skip_update = True
            self._effect = kwargs[ATTR_EFFECT]
            if self._effect == 'HDMI':
                self.json_request({'command': 'clearall'})
                self._icon = 'mdi:video-input-hdmi'
                self._brightness = 255
                self._rgb_color = [125, 125, 125]
            else:
                self.json_request({
                    'command': 'effect',
                    'priority': self._priority,
                    'effect': {'name': self._effect}
                })
                self._icon = 'mdi:lava-lamp'
                self._rgb_color = [175, 0, 255]
            return

        cal_color = [int(round(x*float(brightness)/255))
                     for x in rgb_color]
        self.json_request({
            'command': 'color',
            'priority': self._priority,
            'color': cal_color
        })

    def turn_off(self, **kwargs):
        """Disconnect all remotes."""
        self.json_request({'command': 'clearall'})
        self.json_request({
            'command': 'color',
            'priority': self._priority,
            'color': [0, 0, 0]
        })

    def update(self):
        """Get the lights status."""
        # postpone the immediate state check for changes that take time
        if self._skip_update:
            self._skip_update = False
            return
        response = self.json_request({'command': 'serverinfo'})
        if response:
            # workaround for outdated Hyperion
            if 'activeLedColor' not in response['info']:
                self._rgb_color = self._default_color
                self._rgb_mem = self._default_color
                self._brightness = 255
                self._icon = 'mdi:lightbulb'
                self._effect = None
                return
            # Check if Hyperion is in ambilight mode trough an HDMI grabber
            try:
                active_priority = response['info']['priorities'][0]['priority']
                if active_priority == self._hdmi_priority:
                    self._brightness = 255
                    self._rgb_color = [125, 125, 125]
                    self._icon = 'mdi:video-input-hdmi'
                    self._effect = 'HDMI'
                    return
            except (KeyError, IndexError):
                pass

            led_color = response['info']['activeLedColor']
            if not led_color or led_color[0]['RGB Value'] == [0, 0, 0]:
                # Get the active effect
                if response['info'].get('activeEffects'):
                    self._rgb_color = [175, 0, 255]
                    self._icon = 'mdi:lava-lamp'
                    try:
                        s_name = response['info']['activeEffects'][0]["script"]
                        s_name = s_name.split('/')[-1][:-3].split("-")[0]
                        self._effect = [x for x in self._effect_list
                                        if s_name.lower() in x.lower()][0]
                    except (KeyError, IndexError):
                        self._effect = None
                # Bulb off state
                else:
                    self._rgb_color = [0, 0, 0]
                    self._icon = 'mdi:lightbulb'
                    self._effect = None
            else:
                # Get the RGB color
                self._rgb_color = led_color[0]['RGB Value']
                self._brightness = max(self._rgb_color)
                self._rgb_mem = [int(round(float(x)*255/self._brightness))
                                 for x in self._rgb_color]
                self._icon = 'mdi:lightbulb'
                self._effect = None

    def setup(self):
        """Get the hostname of the remote."""
        response = self.json_request({'command': 'serverinfo'})
        if response:
            if self._name == self._host:
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
