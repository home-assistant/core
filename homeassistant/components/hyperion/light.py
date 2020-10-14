"""Support for Hyperion-NG remotes."""
import asyncio
from functools import partial
import logging
from typing import Any, Callable, Dict, List, Optional, Set

from hyperion import client, const
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.color as color_util

from . import get_hyperion_unique_id, split_hyperion_unique_id
from .const import CONF_INSTANCE, DEFAULT_ORIGIN, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_COLOR = "default_color"
CONF_PRIORITY = "priority"
CONF_HDMI_PRIORITY = "hdmi_priority"
CONF_EFFECT_LIST = "effect_list"

# As we want to preserve brightness control for effects (e.g. to reduce the
# brightness for V4L), we need to persist the effect that is in flight, so
# subsequent calls to turn_on will know the keep the effect enabled.
# Unfortunately the Home Assistant UI does not easily expose a way to remove a
# selected effect (there is no 'No Effect' option by default). Instead, we
# create a new fake effect ("Solid") that is always selected by default for
# showing a solid color. This is the same method used by WLED.
KEY_EFFECT_SOLID = "Solid"

# TODO: Test this.
KEY_ENTRY_ID_PLATFORM = "PLATFORM"

DEFAULT_COLOR = [255, 255, 255]
DEFAULT_BRIGHTNESS = 255
DEFAULT_EFFECT = KEY_EFFECT_SOLID
DEFAULT_NAME = "Hyperion"
DEFAULT_PORT = const.DEFAULT_PORT_JSON
DEFAULT_PRIORITY = 128
DEFAULT_HDMI_PRIORITY = 880
DEFAULT_EFFECT_LIST = []

SUPPORT_HYPERION = SUPPORT_COLOR | SUPPORT_BRIGHTNESS | SUPPORT_EFFECT

# Usage of YAML for configuration of the Hyperion component is deprecated.
PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HOST, invalidation_version="0.118"),
    cv.deprecated(CONF_PORT, invalidation_version="0.118"),
    cv.deprecated(CONF_DEFAULT_COLOR, invalidation_version="0.118"),
    cv.deprecated(CONF_NAME, invalidation_version="0.118"),
    cv.deprecated(CONF_PRIORITY, invalidation_version="0.118"),
    cv.deprecated(CONF_EFFECT_LIST, invalidation_version="0.118"),
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
            vol.Optional(CONF_EFFECT_LIST, default=DEFAULT_EFFECT_LIST): vol.All(
                cv.ensure_list, [cv.string]
            ),
        }
    ),
)

ICON_LIGHTBULB = "mdi:lightbulb"
ICON_EFFECT = "mdi:lava-lamp"
ICON_EXTERNAL_SOURCE = "mdi:television-ambient-light"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Hyperion platform.."""
    await async_setup(
        hass,
        KEY_ENTRY_ID_PLATFORM,
        async_add_entities,
        config.get(CONF_HOST),
        config.get(CONF_PORT),
        name=config.get(CONF_NAME),
        priority=config.get(CONF_PRIORITY),
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Hyperion platform from config entry."""
    # TODO: Add support for varying the priority via an option flow.
    await async_setup(
        hass,
        config_entry.entry_id,
        async_add_entities,
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_PORT],
        token=config_entry.data.get(CONF_TOKEN),
    )


async def async_setup(
    hass: HomeAssistant,
    entry_id: str,
    async_add_entities: Callable,
    host: str,
    port: int,
    name: Optional[str] = None,
    token: Optional[str] = None,
    priority: int = DEFAULT_PRIORITY,
):
    """Set up a Hyperion light from a dict of data."""

    async def async_instances_to_entities(
        platform: entity_platform.EntityPlatform,
        server_id: str,
        host: str,
        port: int,
        name: Optional[str],
        token: Optional[str],
        priority: int,
        response: Dict[str, Any],
    ):
        if not response or const.KEY_DATA not in response:
            return
        return await async_instances_to_entities_raw(
            platform,
            server_id,
            host,
            port,
            name,
            token,
            priority,
            response[const.KEY_DATA],
        )

    # TODO: Curry instead of passing all of this shite in again.
    async def async_instances_to_entities_raw(
        platform: entity_platform.EntityPlatform,
        server_id: str,
        host: str,
        port: int,
        name: Optional[str],
        token: Optional[str],
        priority: int,
        instances: Dict[str, Any],
    ):
        registry = await async_get_registry(hass)
        entities_to_add: List[Hyperion] = []
        desired_instance_ids: Set[int] = set()

        # In practice, an instance can be in 3 states as seen by this function:
        #
        #    * Exists, and is running: Add it to hass.
        #    * Exists, but is not running: Cannot add yet, but should not delete it either. It will show up as "unavailable".
        #    * No longer exists: Delete it from hass.

        # Add instances that are missing (instance must be running)
        for instance in instances:
            instance_id = instance.get(const.KEY_INSTANCE)
            if instance_id is None or not instance.get(const.KEY_RUNNING, False):
                continue
            desired_instance_ids.add(instance_id)
            unique_id = get_hyperion_unique_id(server_id, instance_id)
            entity_id = registry.async_get_entity_id(LIGHT_DOMAIN, DOMAIN, unique_id)
            if (
                entity_id is not None and entity_id in platform.entities
            ):  # hass.states.get(entity_id) is not None:
                continue
            await asyncio.sleep(0)

            hyperion_client = await _async_create_connect_client(
                host, port, instance=instance_id, token=token
            )
            if not hyperion_client:
                continue
            entity_name = name or instance.get(const.KEY_FRIENDLY_NAME, DEFAULT_NAME)
            entities_to_add.append(
                Hyperion(unique_id, entity_name, priority, hyperion_client)
            )

        # Delete instances that are no longer present on this server.
        hyperion_entity_ids = list(platform.entities.keys())

        for entity_id in hyperion_entity_ids:
            entity_server_id, instance_id = split_hyperion_unique_id(
                platform.entities[entity_id].unique_id
            )
            if server_id != entity_server_id:
                continue
            if instance_id not in desired_instance_ids:
                await platform.async_remove_entity(entity_id)
                if entity_id in registry.entities:
                    registry.async_remove(entity_id)

        async_add_entities(entities_to_add)

    hyperion_client = await _async_create_connect_client(host, port, token=token)
    if not hyperion_client:
        raise PlatformNotReady
    server_id = await hyperion_client.async_id()
    if not server_id:
        await hyperion_client.async_client_disconnect()
        raise PlatformNotReady
    hass.data[DOMAIN][entry_id] = hyperion_client

    async_instances_callback = partial(
        async_instances_to_entities,
        entity_platform.current_platform.get(),
        server_id,
        host,
        port,
        name,
        token,
        priority,
    )

    hyperion_client.set_callbacks(
        {f"{const.KEY_INSTANCE}-{const.KEY_UPDATE}": async_instances_callback}
    )
    await async_instances_to_entities_raw(
        entity_platform.current_platform.get(),
        server_id,
        host,
        port,
        name,
        token,
        priority,
        hyperion_client.instances,
    )


async def _async_create_connect_client(
    host: str, port: int, instance: int = const.DEFAULT_INSTANCE, token: str = None
):
    """Create and connect a Hyperion Client."""
    hyperion_client = client.HyperionClient(
        host,
        port,
        **{CONF_TOKEN: token, CONF_INSTANCE: instance},
    )

    if not await hyperion_client.async_client_connect():
        return None
    return hyperion_client


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    client = hass.data[DOMAIN].pop(entry.entry_id)
    return await client.async_client_disconnect()


class Hyperion(LightEntity):
    """Representation of a Hyperion remote."""

    def __init__(self, unique_id, name, priority, hyperion_client):
        """Initialize the light."""
        self._unique_id = unique_id
        self._name = name
        self._priority = priority
        self._client = hyperion_client

        # Active state representing the Hyperion instance.
        self._set_internal_state(
            brightness=255, rgb_color=DEFAULT_COLOR, effect=KEY_EFFECT_SOLID
        )
        self._effect_list = []

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
        return self._client.has_loaded_state

    @property
    def unique_id(self):
        """Return a unique id for this instance."""
        return self._unique_id

    async def async_turn_on(self, **kwargs):
        """Turn the lights on."""
        # == Turn device on ==
        # Turn on both ALL (Hyperion itself) and LEDDEVICE. It would be
        # preferable to enable LEDDEVICE after the settings (e.g. brightness,
        # color, effect), but this is not possible due to:
        # https://github.com/hyperion-project/hyperion.ng/issues/967
        if not self.is_on:
            if not await self._client.async_send_set_component(
                **{
                    const.KEY_COMPONENTSTATE: {
                        const.KEY_COMPONENT: const.KEY_COMPONENTID_ALL,
                        const.KEY_STATE: True,
                    }
                }
            ):
                return

            if not await self._client.async_send_set_component(
                **{
                    const.KEY_COMPONENTSTATE: {
                        const.KEY_COMPONENT: const.KEY_COMPONENTID_LEDDEVICE,
                        const.KEY_STATE: True,
                    }
                }
            ):
                return

        # == Get key parameters ==
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        effect = kwargs.get(ATTR_EFFECT, self._effect)
        if ATTR_HS_COLOR in kwargs:
            rgb_color = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
        else:
            rgb_color = self._rgb_color

        # == Set brightness ==
        if self._brightness != brightness:
            if not await self._client.async_send_set_adjustment(
                **{
                    const.KEY_ADJUSTMENT: {
                        const.KEY_BRIGHTNESS: int(
                            round((float(brightness) * 100) / 255)
                        )
                    }
                }
            ):
                return

        # == Set an external source
        if effect and effect in const.KEY_COMPONENTID_EXTERNAL_SOURCES:

            # Clear any color/effect.
            if not await self._client.async_send_clear(
                **{const.KEY_PRIORITY: self._priority}
            ):
                return

            # Turn off all external sources, except the intended.
            for key in const.KEY_COMPONENTID_EXTERNAL_SOURCES:
                if not await self._client.async_send_set_component(
                    **{
                        const.KEY_COMPONENTSTATE: {
                            const.KEY_COMPONENT: key,
                            const.KEY_STATE: effect == key,
                        }
                    }
                ):
                    return

        # == Set an effect
        elif effect and effect != KEY_EFFECT_SOLID:
            # This call should not be necessary, but without it there is no priorities-update issued:
            # https://github.com/hyperion-project/hyperion.ng/issues/992
            if not await self._client.async_send_clear(
                **{const.KEY_PRIORITY: self._priority}
            ):
                return

            if not await self._client.async_send_set_effect(
                **{
                    const.KEY_PRIORITY: self._priority,
                    const.KEY_EFFECT: {const.KEY_NAME: effect},
                    const.KEY_ORIGIN: DEFAULT_ORIGIN,
                }
            ):
                return
        # == Set a color
        else:
            if not await self._client.async_send_set_color(
                **{
                    const.KEY_PRIORITY: self._priority,
                    const.KEY_COLOR: rgb_color,
                    const.KEY_ORIGIN: DEFAULT_ORIGIN,
                }
            ):
                return

    async def async_turn_off(self, **kwargs):
        """Disable the LED output component."""
        if not await self._client.async_send_set_component(
            **{
                const.KEY_COMPONENTSTATE: {
                    const.KEY_COMPONENT: const.KEY_COMPONENTID_LEDDEVICE,
                    const.KEY_STATE: False,
                }
            }
        ):
            return

    def _set_internal_state(self, brightness=None, rgb_color=None, effect=None):
        """Set the internal state."""
        if brightness is not None:
            self._brightness = brightness
        if rgb_color is not None:
            self._rgb_color = rgb_color
        if effect is not None:
            self._effect = effect
            if effect == KEY_EFFECT_SOLID:
                self._icon = ICON_LIGHTBULB
            elif effect in const.KEY_COMPONENTID_EXTERNAL_SOURCES:
                self._icon = ICON_EXTERNAL_SOURCE
            else:
                self._icon = ICON_EFFECT

    def _update_components(self, _=None):
        """Update Hyperion components."""
        self.async_write_ha_state()

    def _update_adjustment(self, _=None):
        """Update Hyperion adjustments."""
        if self._client.adjustment:
            brightness_pct = self._client.adjustment[0].get(
                const.KEY_BRIGHTNESS, DEFAULT_BRIGHTNESS
            )
            if brightness_pct < 0 or brightness_pct > 100:
                return
            self._set_internal_state(
                brightness=int(round((brightness_pct * 255) / float(100)))
            )
            self.async_write_ha_state()

    def _update_priorities(self, _=None):
        """Update Hyperion priorities."""
        visible_priority = self._client.visible_priority
        if visible_priority:
            componentid = visible_priority.get(const.KEY_COMPONENTID)
            if componentid in const.KEY_COMPONENTID_EXTERNAL_SOURCES:
                self._set_internal_state(rgb_color=DEFAULT_COLOR, effect=componentid)
            elif componentid == const.KEY_COMPONENTID_EFFECT:
                # Owner is the effect name.
                # See: https://docs.hyperion-project.org/en/json/ServerInfo.html#priorities
                self._set_internal_state(
                    rgb_color=DEFAULT_COLOR, effect=visible_priority[const.KEY_OWNER]
                )
            elif componentid == const.KEY_COMPONENTID_COLOR:
                self._set_internal_state(
                    rgb_color=visible_priority[const.KEY_VALUE][const.KEY_RGB],
                    effect=KEY_EFFECT_SOLID,
                )
            self.async_write_ha_state()

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
            self.async_write_ha_state()

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

    def _update_client(self, json):
        """Update client connection state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register callbacks when entity added to hass."""
        self._client.set_callbacks(
            {
                f"{const.KEY_ADJUSTMENT}-{const.KEY_UPDATE}": self._update_adjustment,
                f"{const.KEY_COMPONENTS}-{const.KEY_UPDATE}": self._update_components,
                f"{const.KEY_EFFECTS}-{const.KEY_UPDATE}": self._update_effect_list,
                f"{const.KEY_PRIORITIES}-{const.KEY_UPDATE}": self._update_priorities,
                f"{const.KEY_CLIENT}-{const.KEY_UPDATE}": self._update_client,
            }
        )

        # Load initial state.
        self._update_full_state()
        return True

    async def async_will_remove_from_hass(self):
        """Disconnect from server."""
        await self._client.async_client_disconnect()
