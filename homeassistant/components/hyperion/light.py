"""Support for Hyperion-NG remotes."""
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
            vol.Optional(
                CONF_INSTANCE, default=const.DEFAULT_INSTANCE
            ): cv.positive_int,
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

    # Use loop outside of HA's tracked task in order not to delay startup.
    # device = Hyperion(name, host, port, priority, token, instance, hass.loop)
    hyperion_client = client.HyperionClient(
        host, port, token=token, instance=instance, loop=hass.loop
    )

    if not await hyperion_client.async_connect():
        raise PlatformNotReady

    entity = Hyperion(name, priority, hyperion_client)
    await entity.async_setup()
    async_add_entities([entity])


class Hyperion(LightEntity):
    """Representation of a Hyperion remote."""

    def __init__(self, name, priority, client):
        """Initialize the light."""
        self._name = name
        self._priority = priority
        self._client = client

        # TODO: Need to add connect/disconnect callbacks.

        client.set_callbacks(
            {
                f"{const.KEY_ADJUSTMENT}-{const.KEY_UPDATE}": self._update_adjustment,
                f"{const.KEY_COMPONENTS}-{const.KEY_UPDATE}": self._update_components,
                f"{const.KEY_EFFECTS}-{const.KEY_UPDATE}": self._update_effect_list,
                f"{const.KEY_PRIORITIES}-{const.KEY_UPDATE}": self._update_priorities,
            }
        )

        # Active state representing the Hyperion instance.
        self._brightness = 255
        self._effect = KEY_EFFECT_SOLID
        self._effect_list = []
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
        return self._client.is_on()

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
        return (
            self._effect_list
            + const.KEY_COMPONENTID_EXTERNAL_SOURCES
            + [KEY_EFFECT_SOLID]
        )

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_HYPERION

    @property
    def available(self):
        """Return server availability."""
        return self._client.is_connected

    @property
    def unique_id(self):
        """Return a unique id for this instance."""
        return self._client.id

    async def async_turn_on(self, **kwargs):
        """Turn the lights on."""
        _LOGGER.debug("Turning On: %s", kwargs)
        if not self._client.is_connected:
            return

        # == Turn device on ==
        # Turn on both ALL (Hyperion itself) and LEDDEVICE. It would be
        # preferable to enable LEDDEVICE after the settings (e.g. brightness,
        # color, effect), but this is not possible due to:
        # https://github.com/hyperion-project/hyperion.ng/issues/967
        if not self.is_on:
            if not await self._client.async_set_component(
                **{
                    const.KEY_COMPONENTSTATE: {
                        const.KEY_COMPONENT: const.KEY_COMPONENTID_ALL,
                        const.KEY_STATE: True,
                    }
                }
            ):
                return

            # TODO: Do these failures emit errors in the log?
            if not await self._client.async_set_component(
                **{
                    const.KEY_COMPONENTSTATE: {
                        const.KEY_COMPONENT: const.KEY_COMPONENTID_LEDDEVICE,
                        const.KEY_STATE: True,
                    }
                }
            ):
                return

        # == Set brightness ==
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        if self._brightness != brightness:
            if not await self._client.async_set_adjustment(
                **{
                    const.KEY_ADJUSTMENT: {
                        const.KEY_BRIGHTNESS: int(round((float(brightness) * 100) / 255))
                    }
                }
            ):
                return

        effect = kwargs.get(ATTR_EFFECT, self._effect)
        if effect and effect in const.KEY_COMPONENTID_EXTERNAL_SOURCES:
            # Clear any color/effect.
            if not await self._client.async_clear(**{const.KEY_PRIORITY: self._priority}):
                return

            # Turn off all external sources, except the intended.
            for key in const.KEY_COMPONENTID_EXTERNAL_SOURCES:
                if not await self._client.async_set_component(
                    **{
                        const.KEY_COMPONENTSTATE: {
                            const.KEY_COMPONENT: key,
                            const.KEY_STATE: effect == key,
                        }
                    }
                ):
                    return
        elif effect and effect != KEY_EFFECT_SOLID:
            # This call should not be necessary, but without it there is no priorities-update issued:
            # https://github.com/hyperion-project/hyperion.ng/issues/992
            if not await self._client.async_clear(**{const.KEY_PRIORITY: self._priority}):
                return

            if not await self._client.async_set_effect(
                **{
                    const.KEY_PRIORITY: self._priority,
                    const.KEY_EFFECT: {const.KEY_NAME: effect},
                    const.KEY_ORIGIN: DEFAULT_ORIGIN,
                }
            ):
                return
        else:
            if ATTR_HS_COLOR in kwargs:
                rgb_color = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            else:
                rgb_color = self._rgb_color

            if not await self._client.async_set_color(
                **{
                    const.KEY_PRIORITY: self._priority,
                    const.KEY_COLOR: rgb_color,
                    const.KEY_ORIGIN: DEFAULT_ORIGIN,
                }
            ):
                return

    async def async_turn_off(self, **kwargs):
        """Disable the LED output component."""
        _LOGGER.debug("Turning Off: %s", kwargs)

        if not self._client.is_connected:
            return

        if not await self._client.async_set_component(
            **{
                const.KEY_COMPONENTSTATE: {
                    const.KEY_COMPONENT: const.KEY_COMPONENTID_LEDDEVICE,
                    const.KEY_STATE: False,
                }
            }
        ):
            return

    def _update_ha_state(self):
        """Update the internal Home Assistant state."""
        if not hasattr(self, 'hass') or self.hass is None:
            return
        self.schedule_update_ha_state()

    def _update_components(self, _=None):
        """Update Hyperion components."""
        self._update_ha_state()

    def _update_adjustment(self, _=None):
        """Update Hyperion adjustments."""
        if self._client.adjustment:
            brightness_pct = self._client.adjustment[0].get(
                const.KEY_BRIGHTNESS, DEFAULT_BRIGHTNESS
            )
            if brightness_pct < 0 or brightness_pct > 100:
                return
            self._brightness = int(round((brightness_pct * 255) / float(100)))
            self._update_ha_state()

    def _update_priorities(self, _=None):
        """Update Hyperion priorities."""
        visible_priority = self._client.visible_priority
        if visible_priority:
            componentid = visible_priority.get(const.KEY_COMPONENTID)
            if componentid in const.KEY_COMPONENTID_EXTERNAL_SOURCES:
                self._rgb_color = DEFAULT_COLOR
                self._icon = ICON_EXTERNAL_SOURCE
                self._effect = componentid
            elif componentid == const.KEY_COMPONENTID_EFFECT:
                self._rgb_color = DEFAULT_COLOR
                self._icon = ICON_EFFECT

                # Owner is the effect name.
                # See: https://docs.hyperion-project.org/en/json/ServerInfo.html#priorities
                self._effect = visible_priority[const.KEY_OWNER]
            elif componentid == const.KEY_COMPONENTID_COLOR:
                self._rgb_color = visible_priority[const.KEY_VALUE][const.KEY_RGB]
                self._icon = ICON_LIGHTBULB
                self._effect = KEY_EFFECT_SOLID
            self._update_ha_state()

    def _update_effect_list(self, _=None):
        """Update Hyperion effects."""
        if not self._client.effects:
            return
        effect_list = []
        for effect in self._client.effects or []:
            if const.KEY_NAME in effect:
                effect_list.append(effect[const.KEY_NAME])
        if effect_list:
            self._effect_list = effect_list
            self._update_ha_state()

    def _update_full_state(self):
        """Update full Hyperion state."""
        self._update_adjustment()
        self._update_priorities()
        self._update_effect_list()

        _LOGGER.debug(
            "Hyperion full state update: On=%s,Brightness=%i,Effect=%s "
            "(%i effects total),Color=%s",
            self.is_on,
            self._brightness,
            self._effect,
            len(self._effect_list),
            self._rgb_color,
        )

    async def async_setup(self):
        """Set up the entity."""
        # Load initial state.
        self._update_full_state()

        # Start "background" task.
        self._client.run()
        return True
