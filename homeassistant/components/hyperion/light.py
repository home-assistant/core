"""Support for Hyperion remotes."""
import aiohttp
import asyncio
import json
import logging
import socket

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    LightEntity,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

CONF_PRIORITY = "priority"
CONF_EFFECT_LIST = "effect_list"

KEY_ADJUSTMENT = "adjustment"
KEY_BRIGHTNESS = "brightness"
KEY_CLEAR = "clear"
KEY_COLOR = "color"
KEY_COMMAND = "command"
KEY_COMPONENT = "component"
KEY_COMPONENTSTATE ="componentstate"
KEY_COMPONENTS = "components"
KEY_EFFECT = "effect"
KEY_EFFECTS = "effects"
KEY_ENABLED = "enabled"
KEY_INFO = "info"
KEY_NAME = "name"
KEY_ORIGIN = "origin"
KEY_OWNER = "owner"
KEY_PRIORITY = "priority"
KEY_PRIORITIES = "priorities"
KEY_RGB = "RGB"
KEY_SERVERINFO = "serverinfo"
KEY_STATE = "state"
KEY_VALUE = "value"
KEY_VISIBLE = "visible"

# ComponentIDs from: https://docs.hyperion-project.org/en/json/Control.html#components-ids-explained
KEY_COMPONENTID = "componentId"
KEY_COMPONENTID_ALL = "ALL"
KEY_COMPONENTID_COLOR = "COLOR"
KEY_COMPONENTID_EFFECT = "EFFECT"
KEY_COMPONENTID_EXTERNAL_SOURCES = ["BOBLIGHTSERVER", "GRABBER", "V4L", "IMAGE", "FLATBUFSERVER", "PROTOSERVER"]
KEY_COMPONENTID_LEDDEVICE = "LEDDEVICE"

# As we want to preserve brightness control for effects (e.g. to reduce the
# brightness for V4L), we need to persist the effect that is in flight, so
# subsequent calls to turn_on will know the keep the effect enabled.
# Unfortunately the Home Assistant UI does not easily expose a way to remove a
# selected effect (there is no 'No Effect' option by default). Instead, we
# create a new fake effect ("Solid") that is always selected by default for
# showing a solid color. This is the same method used by WLED.
KEY_EFFECT_SOLID = "Solid"

DEFAULT_COLOR = [255, 255, 255]
DEFAULT_BRIGHTNESS = 255
DEFAULT_EFFECT = KEY_EFFECT_SOLID
DEFAULT_NAME = "Hyperion"
DEFAULT_ORIGIN = "Home Assistant"
DEFAULT_PORT = 19444
DEFAULT_PRIORITY = 128
SUPPORT_HYPERION = SUPPORT_COLOR | SUPPORT_BRIGHTNESS | SUPPORT_EFFECT

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PRIORITY, default=DEFAULT_PRIORITY): cv.positive_int,
        vol.Optional(CONF_EFFECT_LIST, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Hyperion server remote."""
    name = config[CONF_NAME]
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    priority = config[CONF_PRIORITY]
    effect_list = config[CONF_EFFECT_LIST]

    device = Hyperion(
        name, host, port, priority, effect_list
    )

    if device.setup():
        add_entities([device])


class Hyperion(LightEntity):
    """Representation of a Hyperion remote."""

    def __init__(self, name, host, port, priority, effect_list):
        """Initialize the light."""
        self._host = host
        self._port = port
        self._name = name
        self._priority = priority
        self._rgb_color = DEFAULT_COLOR
        self._brightness = 255
        self._icon = "mdi:lightbulb"
        self._effect_list = effect_list
        self._effect = KEY_EFFECT_SOLID
        self._skip_update = False
        self._on = False

        self._components = {}

        _LOGGER.error('New Hyperion init!')

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
        return self._on

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
        return self._effect_list + KEY_COMPONENTID_EXTERNAL_SOURCES + [KEY_EFFECT_SOLID]

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_HYPERION

    def turn_on(self, **kwargs):
        """Turn the lights on."""
        _LOGGER.debug('On: %s' % kwargs)

        # Skip the next update to avoid a timing clash between this request and
        # the polling.
        self._skip_update = True

        # == Turn device on ==
        # Turn on both ALL (Hyperion itself) and LEDDEVICE. It would be
        # preferable to enable LEDDEVICE after the settings (e.g. brightness,
        # color, effect), but this is not possible due to:
        # https://github.com/hyperion-project/hyperion.ng/issues/967
        self.json_request({
            KEY_COMMAND: KEY_COMPONENTSTATE,
            KEY_COMPONENTSTATE: {
                KEY_COMPONENT: KEY_COMPONENTID_ALL,
                KEY_STATE: True,
            }
        })
        self.json_request({
            KEY_COMMAND: KEY_COMPONENTSTATE,
            KEY_COMPONENTSTATE: {
                KEY_COMPONENT: KEY_COMPONENTID_LEDDEVICE,
                KEY_STATE: True,
            }
        })
        self._on = True

        # == Set brightness ==
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        self.json_request({
            KEY_COMMAND: KEY_ADJUSTMENT,
            KEY_ADJUSTMENT: {
                KEY_BRIGHTNESS: int(round((float(brightness)*100) / 255))
            }
        })
        self._brightness = brightness

        effect = kwargs.get(ATTR_EFFECT, self._effect)
        if effect and effect in KEY_COMPONENTID_EXTERNAL_SOURCES:
            # Clear any color/effect.
            self.json_request({
                KEY_COMMAND: KEY_CLEAR,
                KEY_PRIORITY: self._priority
            })

            # Turn off all external sources, except the intended.
            for key in KEY_COMPONENTID_EXTERNAL_SOURCES:
                self.json_request({
                    KEY_COMMAND: KEY_COMPONENTSTATE,
                    KEY_COMPONENTSTATE: {
                        KEY_COMPONENT: key,
                        KEY_STATE: effect == key,
                    }
                })

            self._icon = "mdi:video-input-hdmi"
        elif effect and effect != KEY_EFFECT_SOLID:
            self.json_request({
                KEY_COMMAND: KEY_EFFECT,
                KEY_PRIORITY: self._priority,
                KEY_EFFECT: { KEY_NAME: effect },
                KEY_ORIGIN: DEFAULT_ORIGIN,
            })
            self._icon = "mdi:lava-lamp"
        else:
            if ATTR_HS_COLOR in kwargs:
                rgb_color = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            else:
                rgb_color = self._rgb_color

            self.json_request({
                KEY_COMMAND: KEY_COLOR,
                KEY_PRIORITY: self._priority,
                KEY_COLOR: rgb_color,
                KEY_ORIGIN: DEFAULT_ORIGIN
            })
            self._rgb_color = rgb_color
            self._icon = "mdi:lightbulb"
        self._effect = effect

    def turn_off(self, **kwargs):
        """Disable the LED output component"""
        self.json_request({
            KEY_COMMAND: KEY_COMPONENTSTATE,
            KEY_COMPONENTSTATE: {
                KEY_COMPONENT: KEY_COMPONENTID_LEDDEVICE,
                KEY_STATE: False
            }
        })
        self._on = False

    def update_components(self, components):
      for component in components:
          if KEY_NAME in component and KEY_ENABLED in component:
              self._components[component[KEY_NAME]] = KEY_ENABLED

      if (KEY_COMPONENTID_ALL in self._components and
          KEY_COMPONENTID_LEDDEVICE in self._components):
          self._on = (self._components[KEY_COMPONENTID_ALL] and
                      self._components[KEY_COMPONENTID_LEDDEVICE])

    def update_adjustments(self, adjustment):
        brightness_pct = adjustment.get(KEY_BRIGHTNESS, DEFAULT_BRIGHTNESS)
        self._brightness = int(round((brightness_pct*255) / float(100)))

    def update_priorities(self, priorities):
        # The visible priority is supposed to be the first returned by the
        # API, but due to a bug the ordering is incorrect search for it instead,
        # see: https://github.com/hyperion-project/hyperion.ng/issues/964
        visible_priority = None
        for priority in priorities:
            if priority.get(KEY_VISIBLE, False):
                visible_priority = priority
                break

        if visible_priority:
            componentid = visible_priority.get(KEY_COMPONENTID)
            if componentid in KEY_COMPONENTID_EXTERNAL_SOURCES:
                self._rgb_color = DEFAULT_COLOR
                self._icon = "mdi:video-input-hdmi"
                self._effect = componentid
            elif componentid == KEY_COMPONENTID_EFFECT:
                self._rgb_color = DEFAULT_COLOR
                self._icon = "mdi:lava-lamp"

                # Owner is the effect name.
                # See: https://docs.hyperion-project.org/en/json/ServerInfo.html#priorities
                self._effect = visible_priority[KEY_OWNER]
            elif componentid == KEY_COMPONENTID_COLOR:
                self._rgb_color = visible_priority[KEY_VALUE][KEY_RGB]
                self._icon = "mdi:lightbulb"
                self._effect = KEY_EFFECT_SOLID

    def update(self):
        """Get the lights status."""
        if self._skip_update:
            self._skip_update = False
            return

        response = self.json_request({KEY_COMMAND: KEY_SERVERINFO})
        if response and KEY_INFO in response:
            info = response[KEY_INFO]

            self.update_components(info.get(KEY_COMPONENTS, []))
            if info.get(KEY_ADJUSTMENT, []):
              self.update_adjustments(info[KEY_ADJUSTMENT][0])
            self.update_priorities(info.get(KEY_PRIORITIES, []))

            _LOGGER.debug(
                'Hyperion update: On=%s,Brightness=%i,Effect=%s,Color=%s' % (
                self._on, self._brightness, self._effect, self._rgb_color))
            return True
        return False

    def setup(self):
        """Get the hostname of the remote."""
        response = self.json_request({KEY_COMMAND: KEY_SERVERINFO})
        effect_list = []
        if response and KEY_INFO in response:
            info = response[KEY_INFO]
            for effect in info.get(KEY_EFFECTS, {}):
                if KEY_NAME in effect:
                    effect_list.append(effect[KEY_NAME])
            if not self._effect_list:
                self._effect_list = effect_list
            return True
        return False

    def json_request(self, request, wait_for_response=False):
        """Communicate with the JSON server."""
        # TODO: Deal with AUTH failures when API authentication is enabled.
        # TODO: Evaluate using a pre-packaged JSON library rather than hand-rolled.
        # TODO: Evaluate using subscription feedback from Hyperion rather than only poll.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        _LOGGER.debug('json_request: %s' % request)
        try:
            sock.connect((self._host, self._port))
        except OSError:
            sock.close()
            return False

        sock.send(bytearray(f"{json.dumps(request)}\n", "utf-8"))
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
