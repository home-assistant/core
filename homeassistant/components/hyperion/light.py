"""Support for Hyperion-NG remotes."""
from __future__ import annotations

import logging
import re
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, cast

from hyperion import client, const
import voluptuous as vol

from homeassistant import data_entry_flow
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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
import homeassistant.util.color as color_util

from . import async_create_connect_hyperion_client, get_hyperion_unique_id
from .const import (
    CONF_ON_UNLOAD,
    CONF_PRIORITY,
    CONF_ROOT_CLIENT,
    DEFAULT_ORIGIN,
    DEFAULT_PRIORITY,
    DOMAIN,
    SIGNAL_INSTANCE_REMOVED,
    SIGNAL_INSTANCES_UPDATED,
    SOURCE_IMPORT,
    TYPE_HYPERION_LIGHT,
)

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_COLOR = "default_color"
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
DEFAULT_HDMI_PRIORITY = 880
DEFAULT_EFFECT_LIST: List[str] = []

SUPPORT_HYPERION = SUPPORT_COLOR | SUPPORT_BRIGHTNESS | SUPPORT_EFFECT

# Usage of YAML for configuration of the Hyperion component is deprecated.
PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HDMI_PRIORITY, invalidation_version="0.118"),
    cv.deprecated(CONF_HOST),
    cv.deprecated(CONF_PORT),
    cv.deprecated(CONF_DEFAULT_COLOR, invalidation_version="0.118"),
    cv.deprecated(CONF_NAME),
    cv.deprecated(CONF_PRIORITY),
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


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
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
    hyperion_client = await async_create_connect_hyperion_client(host, port)
    if not hyperion_client:
        raise PlatformNotReady
    hyperion_id = await hyperion_client.async_sysinfo_id()
    if not hyperion_id:
        raise PlatformNotReady

    future_unique_id = get_hyperion_unique_id(
        hyperion_id, instance, TYPE_HYPERION_LIGHT
    )

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
        if entity.config_entry_id is not None or entity.platform != DOMAIN:
            continue
        result = re.search(rf"([^:]+):(\d+)-{instance}", entity.unique_id)
        if result and result.group(1) == host and int(result.group(2)) == port:
            registry.async_update_entity(entity_id, new_unique_id=future_unique_id)
            break
    else:
        # Possibility 3: This is the first upgrade to the new Hyperion component.
        # No config entry and no entity_registry entry, in which case the CONF_NAME
        # variable will be used as the preferred name. Rather than pollute the config
        # entry with a "suggested name" type variable, instead create an entry in the
        # registry that will subsequently be used when the entity is created with this
        # unique_id.

        # This also covers the case that should not occur in the wild (no config entry,
        # but new style unique_id).
        registry.async_get_or_create(
            domain=LIGHT_DOMAIN,
            platform=DOMAIN,
            unique_id=future_unique_id,
            suggested_object_id=config[CONF_NAME],
        )

    async def migrate_yaml_to_config_entry_and_options(
        host: str, port: int, priority: int
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: host,
                CONF_PORT: port,
            },
        )
        if (
            result["type"] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            or result.get("result") is None
        ):
            _LOGGER.warning(
                "Could not automatically migrate Hyperion YAML to a config entry."
            )
            return
        config_entry = result.get("result")
        options = {**config_entry.options, CONF_PRIORITY: config[CONF_PRIORITY]}
        hass.config_entries.async_update_entry(config_entry, options=options)

        _LOGGER.info(
            "Successfully migrated Hyperion YAML configuration to a config entry."
        )

    # Kick off a config flow to create the config entry.
    hass.async_create_task(
        migrate_yaml_to_config_entry_and_options(host, port, config[CONF_PRIORITY])
    )


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities: Callable
) -> bool:
    """Set up a Hyperion platform from config entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    token = config_entry.data.get(CONF_TOKEN)

    async def async_instances_to_entities(response: Dict[str, Any]) -> None:
        if not response or const.KEY_DATA not in response:
            return
        await async_instances_to_entities_raw(response[const.KEY_DATA])

    async def async_instances_to_entities_raw(instances: List[Dict[str, Any]]) -> None:
        registry = await async_get_registry(hass)
        entities_to_add: List[HyperionLight] = []
        desired_unique_ids: Set[str] = set()
        server_id = cast(str, config_entry.unique_id)

        # In practice, an instance can be in 3 states as seen by this function:
        #
        #    * Exists, and is running: Add it to hass.
        #    * Exists, but is not running: Cannot add yet, but should not delete it either.
        #      It will show up as "unavailable".
        #    * No longer exists: Delete it from hass.

        # Add instances that are missing.
        for instance in instances:
            instance_id = instance.get(const.KEY_INSTANCE)
            if instance_id is None or not instance.get(const.KEY_RUNNING, False):
                continue
            unique_id = get_hyperion_unique_id(
                server_id, instance_id, TYPE_HYPERION_LIGHT
            )
            desired_unique_ids.add(unique_id)
            if unique_id in current_entities:
                continue
            hyperion_client = await async_create_connect_hyperion_client(
                host, port, instance=instance_id, token=token
            )
            if not hyperion_client:
                continue
            current_entities.add(unique_id)
            entities_to_add.append(
                HyperionLight(
                    unique_id,
                    instance.get(const.KEY_FRIENDLY_NAME, DEFAULT_NAME),
                    config_entry.options,
                    hyperion_client,
                )
            )

        # Delete instances that are no longer present on this server.
        for unique_id in current_entities - desired_unique_ids:
            current_entities.remove(unique_id)
            async_dispatcher_send(hass, SIGNAL_INSTANCE_REMOVED.format(unique_id))
            entity_id = registry.async_get_entity_id(LIGHT_DOMAIN, DOMAIN, unique_id)
            if entity_id:
                registry.async_remove(entity_id)

        async_add_entities(entities_to_add)

    # Readability note: This variable is kept alive in the context of the callback to
    # async_instances_to_entities below.
    current_entities: Set[str] = set()

    await async_instances_to_entities_raw(
        hass.data[DOMAIN][config_entry.entry_id][CONF_ROOT_CLIENT].instances,
    )
    hass.data[DOMAIN][config_entry.entry_id][CONF_ON_UNLOAD].append(
        async_dispatcher_connect(
            hass,
            SIGNAL_INSTANCES_UPDATED.format(config_entry.entry_id),
            async_instances_to_entities,
        )
    )
    return True


class HyperionLight(LightEntity):
    """Representation of a Hyperion remote."""

    def __init__(
        self,
        unique_id: str,
        name: str,
        options: MappingProxyType[str, Any],
        hyperion_client: client.HyperionClient,
    ) -> None:
        """Initialize the light."""
        self._unique_id = unique_id
        self._name = name
        self._options = options
        self._client = hyperion_client

        # Active state representing the Hyperion instance.
        self._brightness: int = 255
        self._rgb_color: Sequence[int] = DEFAULT_COLOR
        self._effect: str = KEY_EFFECT_SOLID
        self._icon: str = ICON_LIGHTBULB

        self._effect_list: List[str] = []

    @property
    def should_poll(self) -> bool:
        """Return whether or not this entity should be polled."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the light."""
        return self._name

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self) -> Tuple[float, float]:
        """Return last color value set."""
        return color_util.color_RGB_to_hs(*self._rgb_color)

    @property
    def is_on(self) -> bool:
        """Return true if not black."""
        return bool(self._client.is_on()) and self._client.visible_priority is not None

    @property
    def icon(self) -> str:
        """Return state specific icon."""
        return self._icon

    @property
    def effect(self) -> str:
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self) -> List[str]:
        """Return the list of supported effects."""
        return (
            self._effect_list
            + list(const.KEY_COMPONENTID_EXTERNAL_SOURCES)
            + [KEY_EFFECT_SOLID]
        )

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_HYPERION

    @property
    def available(self) -> bool:
        """Return server availability."""
        return bool(self._client.has_loaded_state)

    @property
    def unique_id(self) -> str:
        """Return a unique id for this instance."""
        return self._unique_id

    def _get_option(self, key: str) -> Any:
        """Get a value from the provided options."""
        defaults = {CONF_PRIORITY: DEFAULT_PRIORITY}
        return self._options.get(key, defaults[key])

    async def async_turn_on(self, **kwargs: Any) -> None:
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
        if ATTR_EFFECT not in kwargs and ATTR_HS_COLOR in kwargs:
            effect = KEY_EFFECT_SOLID
        else:
            effect = kwargs.get(ATTR_EFFECT, self._effect)
        rgb_color: Sequence[int]
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
                **{const.KEY_PRIORITY: self._get_option(CONF_PRIORITY)}
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
                **{const.KEY_PRIORITY: self._get_option(CONF_PRIORITY)}
            ):
                return

            if not await self._client.async_send_set_effect(
                **{
                    const.KEY_PRIORITY: self._get_option(CONF_PRIORITY),
                    const.KEY_EFFECT: {const.KEY_NAME: effect},
                    const.KEY_ORIGIN: DEFAULT_ORIGIN,
                }
            ):
                return
        # == Set a color
        else:
            if not await self._client.async_send_set_color(
                **{
                    const.KEY_PRIORITY: self._get_option(CONF_PRIORITY),
                    const.KEY_COLOR: rgb_color,
                    const.KEY_ORIGIN: DEFAULT_ORIGIN,
                }
            ):
                return

    async def async_turn_off(self, **kwargs: Any) -> None:
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

    def _set_internal_state(
        self,
        brightness: Optional[int] = None,
        rgb_color: Optional[Sequence[int]] = None,
        effect: Optional[str] = None,
    ) -> None:
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

    def _update_components(self, _: Optional[Dict[str, Any]] = None) -> None:
        """Update Hyperion components."""
        self.async_write_ha_state()

    def _update_adjustment(self, _: Optional[Dict[str, Any]] = None) -> None:
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

    def _update_priorities(self, _: Optional[Dict[str, Any]] = None) -> None:
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

    def _update_effect_list(self, _: Optional[Dict[str, Any]] = None) -> None:
        """Update Hyperion effects."""
        if not self._client.effects:
            return
        effect_list: List[str] = []
        for effect in self._client.effects or []:
            if const.KEY_NAME in effect:
                effect_list.append(effect[const.KEY_NAME])
        if effect_list:
            self._effect_list = effect_list
            self.async_write_ha_state()

    def _update_full_state(self) -> None:
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

    def _update_client(self, _: Optional[Dict[str, Any]] = None) -> None:
        """Update client connection state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        assert self.hass
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_INSTANCE_REMOVED.format(self._unique_id),
                self.async_remove,
            )
        )

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

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from server."""
        await self._client.async_client_disconnect()
