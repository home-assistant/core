"""Support for Hyperion-NG remotes."""
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

CONF_PRIORITY = 'priority'
CONF_EFFECT_LIST = 'effect_list'

KEY_ADJUSTMENT = 'adjustment'
KEY_BRIGHTNESS = 'brightness'
KEY_CLEAR = 'clear'
KEY_COLOR = 'color'
KEY_COMMAND = 'command'
KEY_COMPONENT = 'component'
KEY_COMPONENTSTATE ='componentstate'
KEY_COMPONENTS = 'components'
KEY_DATA = 'data'
KEY_EFFECT = 'effect'
KEY_EFFECTS = 'effects'
KEY_ENABLED = 'enabled'
KEY_INFO = 'info'
KEY_NAME = 'name'
KEY_ORIGIN = 'origin'
KEY_OWNER = 'owner'
KEY_PRIORITY = 'priority'
KEY_PRIORITIES = 'priorities'
KEY_RGB = 'RGB'
KEY_SERVERINFO = 'serverinfo'
KEY_SUBSCRIBE = 'subscribe'
KEY_SUCCESS = 'success'
KEY_STATE = 'state'
KEY_UPDATE = 'update'
KEY_VALUE = 'value'
KEY_VISIBLE = 'visible'

# ComponentIDs from: https://docs.hyperion-project.org/en/json/Control.html#components-ids-explained
KEY_COMPONENTID = 'componentId'
KEY_COMPONENTID_ALL = 'ALL'
KEY_COMPONENTID_COLOR = 'COLOR'
KEY_COMPONENTID_EFFECT = 'EFFECT'

KEY_COMPONENTID_EXTERNAL_SOURCES = [
    'BOBLIGHTSERVER',
    'GRABBER',
    'V4L']
KEY_COMPONENTID_LEDDEVICE = 'LEDDEVICE'

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
DEFAULT_NAME = 'Hyperion'
DEFAULT_ORIGIN = 'Home Assistant'
DEFAULT_PORT = 19444
DEFAULT_PRIORITY = 128
DEFAULT_CONNECTION_RETRY_DELAY = 30
DEFAULT_CONNECTION_TIMEOUT_SECS = 5
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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a Hyperion server remote."""
    name = config[CONF_NAME]
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    priority = config[CONF_PRIORITY]
    effect_list = config[CONF_EFFECT_LIST]

    device = Hyperion(name, host, port, priority, effect_list)

    if await device.async_setup(hass):
        async_add_entities([device])


class Hyperion(LightEntity):
    """Representation of a Hyperion remote."""

    def __init__(self, name, host, port, priority, static_effect_list):
        """Initialize the light."""
        self._host = host
        self._port = port
        self._name = name
        self._priority = priority
        self._rgb_color = DEFAULT_COLOR
        self._brightness = 255
        self._icon = "mdi:lightbulb"
        self._static_effect_list = static_effect_list
        self._effect_list = static_effect_list
        self._effect = KEY_EFFECT_SOLID
        self._on = False

        self._components = {}
        self._reader = None
        self._writer = None
        self._server_state_established = False

    @property
    def should_poll(self):
        """Return whether or not this entity should be polled."""
        return False

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

    async def async_turn_on(self, **kwargs):
        """Turn the lights on."""
        _LOGGER.debug('On: %s' % kwargs)
        if not self._server_state_established:
            return False

        # == Turn device on ==
        # Turn on both ALL (Hyperion itself) and LEDDEVICE. It would be
        # preferable to enable LEDDEVICE after the settings (e.g. brightness,
        # color, effect), but this is not possible due to:
        # https://github.com/hyperion-project/hyperion.ng/issues/967
        await self._async_send_json({
            KEY_COMMAND: KEY_COMPONENTSTATE,
            KEY_COMPONENTSTATE: {
                KEY_COMPONENT: KEY_COMPONENTID_ALL,
                KEY_STATE: True,
            }
        })
        await self._async_send_json({
            KEY_COMMAND: KEY_COMPONENTSTATE,
            KEY_COMPONENTSTATE: {
                KEY_COMPONENT: KEY_COMPONENTID_LEDDEVICE,
                KEY_STATE: True,
            }
        })
        self._on = True

        # == Set brightness ==
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        await self._async_send_json({
            KEY_COMMAND: KEY_ADJUSTMENT,
            KEY_ADJUSTMENT: {
                KEY_BRIGHTNESS: int(round((float(brightness)*100) / 255))
            }
        })
        self._brightness = brightness

        effect = kwargs.get(ATTR_EFFECT, self._effect)
        if effect and effect in KEY_COMPONENTID_EXTERNAL_SOURCES:
            # Clear any color/effect.
            await self._async_send_json({
                KEY_COMMAND: KEY_CLEAR,
                KEY_PRIORITY: self._priority
            })

            # Turn off all external sources, except the intended.
            for key in KEY_COMPONENTID_EXTERNAL_SOURCES:
                await self._async_send_json({
                    KEY_COMMAND: KEY_COMPONENTSTATE,
                    KEY_COMPONENTSTATE: {
                        KEY_COMPONENT: key,
                        KEY_STATE: effect == key,
                    }
                })

            self._icon = "mdi:video-input-hdmi"
        elif effect and effect != KEY_EFFECT_SOLID:
            await self._async_send_json({
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

            await self._async_send_json({
                KEY_COMMAND: KEY_COLOR,
                KEY_PRIORITY: self._priority,
                KEY_COLOR: rgb_color,
                KEY_ORIGIN: DEFAULT_ORIGIN
            })
            self._rgb_color = rgb_color
            self._icon = "mdi:lightbulb"
        self._effect = effect
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Disable the LED output component"""
        _LOGGER.debug('Off: %s' % kwargs)

        if not self._server_state_established:
            return False

        await self._async_send_json({
            KEY_COMMAND: KEY_COMPONENTSTATE,
            KEY_COMPONENTSTATE: {
                KEY_COMPONENT: KEY_COMPONENTID_LEDDEVICE,
                KEY_STATE: False
            }
        })
        self._on = False
        self.async_write_ha_state()

    async def _async_update_components(self, components):
      """Update Hyperion components"""
      for component in components:
          if KEY_NAME in component and KEY_ENABLED in component:
              self._components[component[KEY_NAME]] = component[KEY_ENABLED]

      if (KEY_COMPONENTID_ALL in self._components and
          KEY_COMPONENTID_LEDDEVICE in self._components):
          self._on = (self._components[KEY_COMPONENTID_ALL] and
                      self._components[KEY_COMPONENTID_LEDDEVICE])

    async def _async_update_adjustment(self, adjustment):
        """Update Hyperion adjustments"""
        brightness_pct = adjustment.get(KEY_BRIGHTNESS, DEFAULT_BRIGHTNESS)
        self._brightness = int(round((brightness_pct*255) / float(100)))

    async def _async_update_priorities(self, priorities):
        """Update Hyperion priorities"""
        # The visible priority is supposed to be the first returned by the
        # API, but due to a bug the ordering is incorrect search for it
        # instead, see:
        # https://github.com/hyperion-project/hyperion.ng/issues/964
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

    async def _async_update_effect_list(self, effects):
        """Update Hyperion effects"""
        if self._static_effect_list:
          return
        effect_list = []
        for effect in effects:
            if KEY_NAME in effect:
                effect_list.append(effect[KEY_NAME])
        if effect_list:
            self._effect_list = effect_list

    async def _async_update_full_state(self, state):
        """Update full Hyperion state."""
        await self._async_update_components(state.get(KEY_COMPONENTS, []))
        if state.get(KEY_ADJUSTMENT, []):
            await self._async_update_adjustment(state[KEY_ADJUSTMENT][0])
        await self._async_update_priorities(state.get(KEY_PRIORITIES, []))
        await self._async_update_effect_list(state.get(KEY_EFFECTS, []))

        _LOGGER.debug(
            'Hyperion full state update: On=%s,Brightness=%i,Effect=%s '
            '(%i effects total),Color=%s' % (self._on, self._brightness,
            self._effect, len(self._effect_list), self._rgb_color))

    async def _async_create_streams(self):
      """Create streams to the Hyperion server"""
      future_streams = asyncio.open_connection(self._host, self._port)
      try:
          _LOGGER.warning("creating streams!")
          self._reader, self._writer = await asyncio.wait_for(
              future_streams, timeout=DEFAULT_CONNECTION_TIMEOUT_SECS)
          _LOGGER.warning("done creating streams!")
          return True
      except (asyncio.TimeoutError, ConnectionError):
          return False

    async def _async_close_streams(self):
      """Close streams to the Hyperion server"""
      self._writer.close()
      await self._writer.wait_closed()

    async def async_setup(self, hass):
        """Setup the entity"""
        hass.async_create_task(self._async_manage_connection())
        return True

    async def _async_send_json(self, request):
        """Send JSON to the server"""
        _LOGGER.debug("Send to server (%s): %s" % (self._name, request))
        output = json.dumps(request).encode('UTF-8') + b'\n'
        self._writer.write(output)
        await self._writer.drain()

    async def _async_send_initial_state_request(self):
        """Send initial request to fetch server state"""

        # Request full state ('serverinfo') and subscribe to relevant
        # future updates to keep this object state accurate without the need to
        # poll.
        data = {
            KEY_COMMAND: KEY_SERVERINFO,
            KEY_SUBSCRIBE: [
                '%s-%s' % (KEY_ADJUSTMENT, KEY_UPDATE),
                '%s-%s' % (KEY_COMPONENTS, KEY_UPDATE),
                '%s-%s' % (KEY_EFFECTS, KEY_UPDATE),
                '%s-%s' % (KEY_PRIORITIES, KEY_UPDATE),
            ]}
        await self._async_send_json(data)

    # TODO: Deal with AUTH failures when API authentication is enabled.
    async def _async_manage_connection(self):
        """Manage the bidirectional connection to the server"""
        while True:
            if not self._reader or not self._writer:
                if not await self._async_create_streams():
                    _LOGGER.warning(
                        'Could not connect to Hyperion (%s), retrying in %i '
                        'seconds...' % (self._name,
                        DEFAULT_CONNECTION_RETRY_DELAY))
                    await asyncio.sleep(DEFAULT_CONNECTION_RETRY_DELAY)
                    continue

            if not self._server_state_established:
                await self._async_send_initial_state_request()

            resp = await self._reader.readline()
            if not resp:
                _LOGGER.warning(
                    'Connection to Hyperion lost (%s) ...'% self._name)
                await self._async_close_streams()
                self._reader, self._writer = None, None
                self._server_state_established = False
                continue

            _LOGGER.debug('Read from server (%s): %s' % (self._name, resp))

            try:
                resp_json = json.loads(resp)
            except json.decoder.JSONDecodeError:
                _LOGGER.warning(
                    'Could not decode JSON from Hyperion (%s), skipping...' % (
                    self._name))
                continue

            if not KEY_COMMAND in resp_json:
                _LOGGER.warning(
                    'JSON from Hyperion (%s) did not include expected \'%s\' '
                    'parameter, skipping...' % (self._name, KEY_COMMAND))
                continue

            should_update_state = False
            command = resp_json[KEY_COMMAND]
            if command == KEY_SERVERINFO and KEY_INFO in resp_json:
                await self._async_update_full_state(resp_json[KEY_INFO])
                self._server_state_established = True
                should_update_state = True
            elif (command == '%s-%s' % (KEY_COMPONENTS, KEY_UPDATE) and
                  KEY_DATA in resp_json):
                await self._async_update_components([resp_json[KEY_DATA]])
                should_update_state = True
            elif (command == '%s-%s' % (KEY_ADJUSTMENT, KEY_UPDATE) and
                  resp_json.get(KEY_DATA, [])):
                await self._async_update_adjustment(resp_json[KEY_DATA][0])
                should_update_state = True
            elif (command == '%s-%s' % (KEY_EFFECTS, KEY_UPDATE) and
                  resp_json.get(KEY_DATA, [])):
                await self._async_update_effect_list(resp_json[KEY_DATA])
                should_update_state = True
            elif (command == '%s-%s' % (KEY_PRIORITIES, KEY_UPDATE) and
                  resp_json.get(KEY_DATA, {}).get(KEY_PRIORITIES, {})):
                await self._async_update_priorities(
                    resp_json[KEY_DATA][KEY_PRIORITIES])
                should_update_state = True
            elif not resp_json.get(KEY_SUCCESS, True):
                _LOGGER.warning('Failed Hyperion (%s) command: %s' % (
                    self._name, resp_json))

            if should_update_state:
                self.async_write_ha_state()
