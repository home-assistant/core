"""Support for Hyperion-NG remotes."""
import asyncio
import json
import logging

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
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

from hyperion import client, const

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_COLOR = "default_color"
CONF_PRIORITY = "priority"
CONF_HDMI_PRIORITY = "hdmi_priority"
CONF_EFFECT_LIST = "effect_list"
CONF_TOKEN = "token"
CONF_INSTANCE = "instance"

KEY_COMPONENTID_EXTERNAL_SOURCES = [
    const.KEY_COMPONENTID_BOBLIGHTSERVER,
    const.KEY_COMPONENTID_GRABBER,
    const.KEY_COMPONENTID_V4L
]

KEY_COMPONENTID_LEDDEVICE = const.KEY_COMPONENTID_LEDDEVICE

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
DEFAULT_HDMI_PRIORITY = 880

SUPPORT_HYPERION = SUPPORT_COLOR | SUPPORT_BRIGHTNESS | SUPPORT_EFFECT

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HDMI_PRIORITY, invalidation_version="0.115"),
    cv.deprecated(CONF_DEFAULT_COLOR, invalidation_version="0.115"),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_DEFAULT_COLOR, default=DEFAULT_COLOR): vol.All(
                list,
                vol.Length(min=3, max=3),
                [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))],
            ),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_PRIORITY, default=DEFAULT_PRIORITY): cv.positive_int,
            vol.Optional(
                CONF_HDMI_PRIORITY, default=DEFAULT_HDMI_PRIORITY
            ): cv.positive_int,
            vol.Optional(CONF_EFFECT_LIST, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONF_TOKEN): cv.string,
            vol.Optional(CONF_INSTANCE, default=DEFAULT_INSTANCE): cv.positive_int,
        }
    ),
)

ICON_LIGHTBULB = "mdi:lightbulb"
ICON_EFFECT = "mdi:lava-lamp"
ICON_EXTERNAL_SOURCE = "mdi:video-input-hdmi"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a Hyperion server remote."""
    name = config[CONF_NAME]
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    priority = config[CONF_PRIORITY]
    token = config.get(CONF_TOKEN)
    instance = config.get(CONF_INSTANCE)

    device = Hyperion(name, host, port, priority, token, instance)

    if not await device.async_setup(hass):
        raise PlatformNotReady
    else:
        async_add_entities([device])


class Hyperion(LightEntity):
    """Representation of a Hyperion remote."""

    def __init__(self, name, host, port, priority, token, instance):
        """Initialize the light."""
        self._hyperion_client = client(host, port, token=token, instance=instance)
        self._name = name
        self._priority = priority

        # Active state representing the Hyperion instance.
        self._brightness = 255
        self._effect = KEY_EFFECT_SOLID
        self._icon = ICON_LIGHTBULB
        self._rgb_color = DEFAULT_COLOR

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
        return self._hyperion_client.is_on()

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

    @property
    def available(self):
        """Return server availability."""
        return self._hyperion_client.is_connected

    @property
    def unique_id(self):
        """Return a unique id for this instance."""
        return "%s:%i-%i" % (self._host, self._port, self._instance)

    async def async_turn_on(self, **kwargs):
        """Turn the lights on."""
        _LOGGER.debug("Turning On: %s", kwargs)
        if not self._is_connected:
            return False

        # == Turn device on ==
        # Turn on both ALL (Hyperion itself) and LEDDEVICE. It would be
        # preferable to enable LEDDEVICE after the settings (e.g. brightness,
        # color, effect), but this is not possible due to:
        # https://github.com/hyperion-project/hyperion.ng/issues/967
        await self._async_send_json(
            {
                KEY_COMMAND: KEY_COMPONENTSTATE,
                KEY_COMPONENTSTATE: {
                    KEY_COMPONENT: KEY_COMPONENTID_ALL,
                    KEY_STATE: True,
                },
            }
        )
        await self._async_send_json(
            {
                KEY_COMMAND: KEY_COMPONENTSTATE,
                KEY_COMPONENTSTATE: {
                    KEY_COMPONENT: KEY_COMPONENTID_LEDDEVICE,
                    KEY_STATE: True,
                },
            }
        )
        self._on = True

        # == Set brightness ==
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        await self._async_send_json(
            {
                KEY_COMMAND: KEY_ADJUSTMENT,
                KEY_ADJUSTMENT: {
                    KEY_BRIGHTNESS: int(round((float(brightness) * 100) / 255))
                },
            }
        )
        self._brightness = brightness

        effect = kwargs.get(ATTR_EFFECT, self._effect)
        if effect and effect in KEY_COMPONENTID_EXTERNAL_SOURCES:
            # Clear any color/effect.
            await self._async_send_json(
                {KEY_COMMAND: KEY_CLEAR, KEY_PRIORITY: self._priority}
            )

            # Turn off all external sources, except the intended.
            for key in KEY_COMPONENTID_EXTERNAL_SOURCES:
                await self._async_send_json(
                    {
                        KEY_COMMAND: KEY_COMPONENTSTATE,
                        KEY_COMPONENTSTATE: {
                            KEY_COMPONENT: key,
                            KEY_STATE: effect == key,
                        },
                    }
                )

            self._icon = ICON_EXTERNAL_SOURCE
        elif effect and effect != KEY_EFFECT_SOLID:
            await self._async_send_json(
                {
                    KEY_COMMAND: KEY_EFFECT,
                    KEY_PRIORITY: self._priority,
                    KEY_EFFECT: {KEY_NAME: effect},
                    KEY_ORIGIN: DEFAULT_ORIGIN,
                }
            )
            self._icon = ICON_EFFECT
        else:
            if ATTR_HS_COLOR in kwargs:
                rgb_color = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            else:
                rgb_color = self._rgb_color

            await self._async_send_json(
                {
                    KEY_COMMAND: KEY_COLOR,
                    KEY_PRIORITY: self._priority,
                    KEY_COLOR: rgb_color,
                    KEY_ORIGIN: DEFAULT_ORIGIN,
                }
            )
            self._rgb_color = rgb_color
            self._icon = ICON_LIGHTBULB
        self._effect = effect
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Disable the LED output component."""
        _LOGGER.debug("Turning Off: %s", kwargs)

        if not self._is_connected:
            return False

        await self._async_send_json(
            {
                KEY_COMMAND: KEY_COMPONENTSTATE,
                KEY_COMPONENTSTATE: {
                    KEY_COMPONENT: KEY_COMPONENTID_LEDDEVICE,
                    KEY_STATE: False,
                },
            }
        )
        self._on = False
        self.async_write_ha_state()

    async def _async_update_components(self, components):
        """Update Hyperion components."""
        for component in components:
            if KEY_NAME in component and KEY_ENABLED in component:
                self._components[component[KEY_NAME]] = component[KEY_ENABLED]

        if (
            KEY_COMPONENTID_ALL in self._components
            and KEY_COMPONENTID_LEDDEVICE in self._components
        ):
            self._on = (
                self._components[KEY_COMPONENTID_ALL]
                and self._components[KEY_COMPONENTID_LEDDEVICE]
            )

    async def _async_update_adjustment(self, adjustment):
        """Update Hyperion adjustments."""
        brightness_pct = adjustment.get(KEY_BRIGHTNESS, DEFAULT_BRIGHTNESS)
        self._brightness = int(round((brightness_pct * 255) / float(100)))

    async def _async_update_priorities(self, priorities):
        """Update Hyperion priorities."""
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
                self._icon = ICON_EXTERNAL_SOURCE
                self._effect = componentid
            elif componentid == KEY_COMPONENTID_EFFECT:
                self._rgb_color = DEFAULT_COLOR
                self._icon = ICON_EFFECT

                # Owner is the effect name.
                # See: https://docs.hyperion-project.org/en/json/ServerInfo.html#priorities
                self._effect = visible_priority[KEY_OWNER]
            elif componentid == KEY_COMPONENTID_COLOR:
                self._rgb_color = visible_priority[KEY_VALUE][KEY_RGB]
                self._icon = ICON_LIGHTBULB
                self._effect = KEY_EFFECT_SOLID

    async def _async_update_effect_list(self, effects):
        """Update Hyperion effects."""
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
            "Hyperion full state update: On=%s,Brightness=%i,Effect=%s "
            "(%i effects total),Color=%s",
            self._on,
            self._brightness,
            self._effect,
            len(self._effect_list),
            self._rgb_color,
        )

    async def _async_connect(self):
        """Connect to the Hyperion server."""
        future_streams = asyncio.open_connection(self._host, self._port)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                future_streams, timeout=DEFAULT_CONNECTION_TIMEOUT_SECS
            )
        except (asyncio.TimeoutError, ConnectionError):
            return False

        _LOGGER.debug(
            "Connected to Hyperion server (%s): %s:%i",
            self._name,
            self._host,
            self._port,
        )

        # == Request: authorize ==
        if self._token is not None:
            data = {
                KEY_COMMAND: KEY_AUTHORIZE,
                KEY_SUBCOMMAND: KEY_LOGIN,
                KEY_TOKEN: self._token,
            }
            await self._async_send_json(data)
            resp_json = await self._async_safely_read_command()
            if (
                not resp_json
                or resp_json.get(KEY_COMMAND) != KEY_AUTHORIZE_LOGIN
                or not resp_json.get(KEY_SUCCESS, False)
            ):
                _LOGGER.warning(
                    "Authorization failed for Hyperion (%s). "
                    "Check token is valid: %s",
                    self._name,
                    resp_json,
                )
                return False

        # == Request: instance ==
        if self._instance != 0:
            data = {
                KEY_COMMAND: KEY_INSTANCE,
                KEY_SUBCOMMAND: KEY_SWITCH_TO,
                KEY_INSTANCE: self._instance,
            }
            await self._async_send_json(data)
            resp_json = await self._async_safely_read_command()
            if (
                not resp_json
                or resp_json.get(KEY_COMMAND) != (f"{KEY_INSTANCE}-{KEY_SWITCH_TO}")
                or not resp_json.get(KEY_SUCCESS, False)
            ):
                _LOGGER.warning(
                    "Changing instqnce failed for Hyperion (%s): %s ",
                    self._name,
                    resp_json,
                )
                return False

        # == Request: serverinfo ==
        # Request full state ('serverinfo') and subscribe to relevant
        # future updates to keep this object state accurate without the need to
        # poll.
        data = {
            KEY_COMMAND: KEY_SERVERINFO,
            KEY_SUBSCRIBE: [
                f"{KEY_ADJUSTMENT}-{KEY_UPDATE}",
                f"{KEY_COMPONENTS}-{KEY_UPDATE}",
                f"{KEY_EFFECTS}-{KEY_UPDATE}",
                f"{KEY_INSTANCE}-{KEY_UPDATE}",
                f"{KEY_PRIORITIES}-{KEY_UPDATE}",
            ],
        }

        await self._async_send_json(data)
        resp_json = await self._async_safely_read_command()
        if (
            not resp_json
            or resp_json.get(KEY_COMMAND) != KEY_SERVERINFO
            or not resp_json.get(KEY_INFO)
            or not resp_json.get(KEY_SUCCESS, False)
        ):
            _LOGGER.warning(
                "Could not load initial state for Hyperion (%s): %s",
                self._name,
                resp_json,
            )
            return False

        await self._async_update_full_state(resp_json[KEY_INFO])
        self._is_connected = True
        self.async_write_ha_state()
        return True

    async def _async_close_streams(self):
        """Close streams to the Hyperion server."""
        self._is_connected = False
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader, self._writer = None, None
        self.async_write_ha_state()

    async def async_setup(self, hass):
        """Set up the entity."""
        # Create connection attempt outside of HA's tracked task in order not
        # to delay startup.
        hass.loop.create_task(self._async_manage_connection())
        return True

    async def _async_send_json(self, request):
        """Send JSON to the server."""
        _LOGGER.debug("Send to server (%s): %s", self._name, request)
        output = json.dumps(request).encode("UTF-8") + b"\n"
        self._writer.write(output)
        await self._writer.drain()

    async def _async_safely_read_command(self):
        """Safely read a command from the stream."""
        connection_error = False
        try:
            resp = await self._reader.readline()
        except ConnectionError:
            connection_error = True

        if connection_error or not resp:
            _LOGGER.warning("Connection to Hyperion lost (%s) ...", self._name)
            await self._async_close_streams()
            return None

        _LOGGER.debug("Read from server (%s): %s", self._name, resp)

        try:
            resp_json = json.loads(resp)
        except json.decoder.JSONDecodeError:
            _LOGGER.warning(
                "Could not decode JSON from Hyperion (%s), skipping...", self._name
            )
            return None

        if KEY_COMMAND not in resp_json:
            _LOGGER.warning(
                "JSON from Hyperion (%s) did not include expected '%s' "
                "parameter, skipping...",
                self._name,
                KEY_COMMAND,
            )
            return None
        return resp_json

    async def _async_verify_instance_or_close(self, instances):
        """Verify the instance still exists on the server."""
        for instance in instances:
            if instance[KEY_INSTANCE] == self._instance:
                return

        # If the instance this entity is using no longer exists, close the
        # connection immediately (as the instance used in the connection may
        # change, so controls would impact a different instance). See caution
        # note here:
        #
        # https://docs.hyperion-project.org/en/json/Control.html#api-instance-handling

        _LOGGER.warning(
            "Hyperion (%s) instance %i disappeared, closing connection ...",
            self._name,
            self._instance,
        )
        await self._async_close_streams()

    async def _async_manage_connection(self):
        """Manage the bidirectional connection to the server."""
        while True:
            if not self._is_connected:
                if not await self._async_connect():
                    _LOGGER.warning(
                        "Could not estalish valid connection to Hyperion (%s), "
                        "retrying in %i seconds...",
                        self._name,
                        DEFAULT_CONNECTION_RETRY_DELAY,
                    )
                    await self._async_close_streams()
                    await asyncio.sleep(DEFAULT_CONNECTION_RETRY_DELAY)
                    continue

            resp_json = await self._async_safely_read_command()
            if not resp_json:
                continue
            command = resp_json[KEY_COMMAND]

            should_update_state = True
            if not resp_json.get(KEY_SUCCESS, True):
                _LOGGER.warning(
                    "Failed Hyperion (%s) command: %s", self._name, resp_json
                )
                should_update_state = False
            elif command == f"{KEY_COMPONENTS}-{KEY_UPDATE}" and KEY_DATA in resp_json:
                await self._async_update_components([resp_json[KEY_DATA]])
            elif command == f"{KEY_ADJUSTMENT}-{KEY_UPDATE}" and resp_json.get(
                KEY_DATA, []
            ):
                await self._async_update_adjustment(resp_json[KEY_DATA][0])
            elif command == f"{KEY_EFFECTS}-{KEY_UPDATE}" and resp_json.get(
                KEY_DATA, []
            ):
                await self._async_update_effect_list(resp_json[KEY_DATA])
            elif command == f"{KEY_PRIORITIES}-{KEY_UPDATE}" and resp_json.get(
                KEY_DATA, {}
            ).get(KEY_PRIORITIES, {}):
                await self._async_update_priorities(resp_json[KEY_DATA][KEY_PRIORITIES])
            elif command == f"{KEY_INSTANCE}-{KEY_UPDATE}" and KEY_DATA in resp_json:
                await self._async_verify_instance_or_close(resp_json[KEY_DATA])
                should_update_state = False

            if should_update_state:
                self.async_write_ha_state()
