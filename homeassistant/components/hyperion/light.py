"""Support for Hyperion-NG remotes."""
from functools import partial
import logging
import re
from typing import Any, Dict, List, Set

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
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.color as color_util

from . import get_hyperion_unique_id, split_hyperion_unique_id
from .const import CONF_INSTANCE, DEFAULT_ORIGIN, DOMAIN, SOURCE_IMPORT

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

KEY_ENTRY_ID_YAML = "YAML"

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

    # This is the entrypoint for the old YAML-style Hyperion integration. The goal here
    # is to auto-convert the YAML configuration into a config entry, with no human
    # interaction, preserving the entity_id. This should be possible, as the YAML
    # configuration did not support any of the things that should otherwise require
    # human interaction in the config flow (e.g. it did not support auth).

    host = config[CONF_HOST]
    port = config[CONF_PORT]
    instance = 0  # YAML only supports a single instance.

    # First, connect to the server and get the server id (which will be unique_id on a config_entry
    # if there is one).
    hyperion_client = await _async_create_connect_client(host, port)
    if not hyperion_client:
        raise PlatformNotReady
    hyperion_id = await hyperion_client.async_id()
    if not hyperion_id:
        raise PlatformNotReady

    future_unique_id = get_hyperion_unique_id(hyperion_id, instance)

    # Possibility 1: Already converted.
    # There is already a config entry with the unique id reporting by the
    # server. Nothing to do here.
    for entry in hass.config_entries.async_entries(domain=DOMAIN):
        if entry.unique_id == hyperion_id:
            return

    # Possibility 2: Upgraded to the new Hyperion component pre-config-flow.
    # No config entry for this unique_id, but have an entity_registry entry
    # with an old-style unique_id:
    #     <host>:<port>-<instance> (instance will always be 0, as YAML
    #                               configuration does not support multiple
    #                               instances)
    # The unique_id needs to be updated, then the config_flow should do the rest.
    registry = await async_get_registry(hass)
    for entity_id, entity in registry.entities.items():
        if entity.config_entry_id is None and entity.platform == DOMAIN:
            result = re.search(r"([^:]+):(\d+)-%i" % instance, entity.unique_id)
            if result and result.group(0) == host and int(result.group(1)) == port:
                registry.async_update_entity(entity_id, new_unique_id=future_unique_id)
                break
    else:
        # Possibility 3: First upgrade to the new Hyperion component.
        # No config entry and no entity_registry entry, in which case the CONF_NAME
        # variable will be used as the preferred name. Rather than pollute the config
        # entry with a "suggested name" type variable, instead create an entry in the
        # registry that will subsequently be used when the entity is created with this
        # unique_id.
        current_platform = entity_platform.current_platform.get()
        registry.async_get_or_create(
            domain=LIGHT_DOMAIN,
            platform=DOMAIN,
            unique_id=future_unique_id,
            suggested_object_id=config[CONF_NAME],
            known_object_ids=current_platform.entities.keys(),
        )

    # Kick off a config flow to create the config entry.
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: config.get(CONF_HOST),
                CONF_PORT: config.get(CONF_HOST),
            },
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Hyperion platform from config entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    token = config_entry.data.get(CONF_TOKEN)

    # TODO: Add support for varying the priority via an option flow.
    priority = DEFAULT_PRIORITY

    async def async_instances_to_entities(
        platform: entity_platform.EntityPlatform,
        response: Dict[str, Any],
    ):
        if not response or const.KEY_DATA not in response:
            return
        return await async_instances_to_entities_raw(
            platform,
            response[const.KEY_DATA],
        )

    async def async_instances_to_entities_raw(
        platform: entity_platform.EntityPlatform,
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
            if entity_id is not None and entity_id in platform.entities:
                continue
            hyperion_client = await _async_create_connect_client(
                host, port, instance=instance_id, token=token
            )
            if not hyperion_client:
                continue
            entity_name = instance.get(const.KEY_FRIENDLY_NAME, DEFAULT_NAME)
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
    hass.data[DOMAIN][config_entry.entry_id] = hyperion_client

    hyperion_client.set_callbacks(
        {
            f"{const.KEY_INSTANCE}-{const.KEY_UPDATE}": partial(
                async_instances_to_entities, entity_platform.current_platform.get()
            )
        }
    )

    await async_instances_to_entities_raw(
        entity_platform.current_platform.get(),
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
    hyperion_client = hass.data[DOMAIN].pop(entry.entry_id)
    return await hyperion_client.async_client_disconnect()


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
