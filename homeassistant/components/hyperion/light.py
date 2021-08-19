"""Support for Hyperion-NG remotes."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import functools
import logging
from types import MappingProxyType
from typing import Any, Callable

from hyperion import client, const

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from . import (
    get_hyperion_device_id,
    get_hyperion_unique_id,
    listen_for_instance_updates,
)
from .const import (
    CONF_EFFECT_HIDE_LIST,
    CONF_INSTANCE_CLIENTS,
    CONF_PRIORITY,
    DEFAULT_ORIGIN,
    DEFAULT_PRIORITY,
    DOMAIN,
    HYPERION_MANUFACTURER_NAME,
    HYPERION_MODEL_NAME,
    NAME_SUFFIX_HYPERION_LIGHT,
    NAME_SUFFIX_HYPERION_PRIORITY_LIGHT,
    SIGNAL_ENTITY_REMOVE,
    TYPE_HYPERION_LIGHT,
    TYPE_HYPERION_PRIORITY_LIGHT,
)

_LOGGER = logging.getLogger(__name__)

COLOR_BLACK = color_util.COLORS["black"]

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

DEFAULT_COLOR = [255, 255, 255]
DEFAULT_BRIGHTNESS = 255
DEFAULT_EFFECT = KEY_EFFECT_SOLID
DEFAULT_NAME = "Hyperion"
DEFAULT_PORT = const.DEFAULT_PORT_JSON
DEFAULT_HDMI_PRIORITY = 880
DEFAULT_EFFECT_LIST: list[str] = []

SUPPORT_HYPERION = SUPPORT_COLOR | SUPPORT_BRIGHTNESS | SUPPORT_EFFECT

ICON_LIGHTBULB = "mdi:lightbulb"
ICON_EFFECT = "mdi:lava-lamp"
ICON_EXTERNAL_SOURCE = "mdi:television-ambient-light"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up a Hyperion platform from config entry."""

    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    server_id = config_entry.unique_id

    @callback
    def instance_add(instance_num: int, instance_name: str) -> None:
        """Add entities for a new Hyperion instance."""
        assert server_id
        args = (
            server_id,
            instance_num,
            instance_name,
            config_entry.options,
            entry_data[CONF_INSTANCE_CLIENTS][instance_num],
        )
        async_add_entities(
            [
                HyperionLight(*args),
                HyperionPriorityLight(*args),
            ]
        )

    @callback
    def instance_remove(instance_num: int) -> None:
        """Remove entities for an old Hyperion instance."""
        assert server_id
        for light_type in LIGHT_TYPES:
            async_dispatcher_send(
                hass,
                SIGNAL_ENTITY_REMOVE.format(
                    get_hyperion_unique_id(server_id, instance_num, light_type)
                ),
            )

    listen_for_instance_updates(hass, config_entry, instance_add, instance_remove)
    return True


class HyperionBaseLight(LightEntity):
    """A Hyperion light base class."""

    def __init__(
        self,
        server_id: str,
        instance_num: int,
        instance_name: str,
        options: MappingProxyType[str, Any],
        hyperion_client: client.HyperionClient,
    ) -> None:
        """Initialize the light."""
        self._unique_id = self._compute_unique_id(server_id, instance_num)
        self._name = self._compute_name(instance_name)
        self._device_id = get_hyperion_device_id(server_id, instance_num)
        self._instance_name = instance_name
        self._options = options
        self._client = hyperion_client

        # Active state representing the Hyperion instance.
        self._brightness: int = 255
        self._rgb_color: Sequence[int] = DEFAULT_COLOR
        self._effect: str = KEY_EFFECT_SOLID

        self._static_effect_list: list[str] = [KEY_EFFECT_SOLID]
        if self._support_external_effects:
            self._static_effect_list += [
                const.KEY_COMPONENTID_TO_NAME[component]
                for component in const.KEY_COMPONENTID_EXTERNAL_SOURCES
            ]
        self._effect_list: list[str] = self._static_effect_list[:]

        self._client_callbacks: Mapping[str, Callable[[dict[str, Any]], None]] = {
            f"{const.KEY_ADJUSTMENT}-{const.KEY_UPDATE}": self._update_adjustment,
            f"{const.KEY_COMPONENTS}-{const.KEY_UPDATE}": self._update_components,
            f"{const.KEY_EFFECTS}-{const.KEY_UPDATE}": self._update_effect_list,
            f"{const.KEY_PRIORITIES}-{const.KEY_UPDATE}": self._update_priorities,
            f"{const.KEY_CLIENT}-{const.KEY_UPDATE}": self._update_client,
        }

    def _compute_unique_id(self, server_id: str, instance_num: int) -> str:
        """Compute a unique id for this instance."""
        raise NotImplementedError

    def _compute_name(self, instance_name: str) -> str:
        """Compute the name of the light."""
        raise NotImplementedError

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Whether or not the entity is enabled by default."""
        return True

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
    def hs_color(self) -> tuple[float, float]:
        """Return last color value set."""
        return color_util.color_RGB_to_hs(*self._rgb_color)

    @property
    def icon(self) -> str:
        """Return state specific icon."""
        if self.is_on:
            if (
                self.effect in const.KEY_COMPONENTID_FROM_NAME
                and const.KEY_COMPONENTID_FROM_NAME[self.effect]
                in const.KEY_COMPONENTID_EXTERNAL_SOURCES
            ):
                return ICON_EXTERNAL_SOURCE
            if self.effect != KEY_EFFECT_SOLID:
                return ICON_EFFECT
        return ICON_LIGHTBULB

    @property
    def effect(self) -> str:
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return self._effect_list

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

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._instance_name,
            "manufacturer": HYPERION_MANUFACTURER_NAME,
            "model": HYPERION_MODEL_NAME,
        }

    def _get_option(self, key: str) -> Any:
        """Get a value from the provided options."""
        defaults = {
            CONF_PRIORITY: DEFAULT_PRIORITY,
            CONF_EFFECT_HIDE_LIST: [],
        }
        return self._options.get(key, defaults[key])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # == Get key parameters ==
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
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            for item in self._client.adjustment or []:
                if (
                    const.KEY_ID in item
                    and not await self._client.async_send_set_adjustment(
                        **{
                            const.KEY_ADJUSTMENT: {
                                const.KEY_BRIGHTNESS: int(
                                    round((float(brightness) * 100) / 255)
                                ),
                                const.KEY_ID: item[const.KEY_ID],
                            }
                        }
                    )
                ):
                    return

        # == Set an external source
        if (
            effect
            and self._support_external_effects
            and (
                effect in const.KEY_COMPONENTID_EXTERNAL_SOURCES
                or effect in const.KEY_COMPONENTID_FROM_NAME
            )
        ):
            if effect in const.KEY_COMPONENTID_FROM_NAME:
                component = const.KEY_COMPONENTID_FROM_NAME[effect]
            else:
                _LOGGER.warning(
                    "Use of Hyperion effect '%s' is deprecated and will be removed "
                    "in a future release. Please use '%s' instead",
                    effect,
                    const.KEY_COMPONENTID_TO_NAME[effect],
                )
                component = effect

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
                            const.KEY_STATE: component == key,
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

    def _set_internal_state(
        self,
        brightness: int | None = None,
        rgb_color: Sequence[int] | None = None,
        effect: str | None = None,
    ) -> None:
        """Set the internal state."""
        if brightness is not None:
            self._brightness = brightness
        if rgb_color is not None:
            self._rgb_color = rgb_color
        if effect is not None:
            self._effect = effect

    @callback
    def _update_components(self, _: dict[str, Any] | None = None) -> None:
        """Update Hyperion components."""
        self.async_write_ha_state()

    @callback
    def _update_adjustment(self, _: dict[str, Any] | None = None) -> None:
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

    @callback
    def _update_priorities(self, _: dict[str, Any] | None = None) -> None:
        """Update Hyperion priorities."""
        priority = self._get_priority_entry_that_dictates_state()
        if priority and self._allow_priority_update(priority):
            componentid = priority.get(const.KEY_COMPONENTID)
            if (
                self._support_external_effects
                and componentid in const.KEY_COMPONENTID_EXTERNAL_SOURCES
                and componentid in const.KEY_COMPONENTID_TO_NAME
            ):
                self._set_internal_state(
                    rgb_color=DEFAULT_COLOR,
                    effect=const.KEY_COMPONENTID_TO_NAME[componentid],
                )
            elif componentid == const.KEY_COMPONENTID_EFFECT:
                # Owner is the effect name.
                # See: https://docs.hyperion-project.org/en/json/ServerInfo.html#priorities
                self._set_internal_state(
                    rgb_color=DEFAULT_COLOR, effect=priority[const.KEY_OWNER]
                )
            elif componentid == const.KEY_COMPONENTID_COLOR:
                self._set_internal_state(
                    rgb_color=priority[const.KEY_VALUE][const.KEY_RGB],
                    effect=KEY_EFFECT_SOLID,
                )
        self.async_write_ha_state()

    @callback
    def _update_effect_list(self, _: dict[str, Any] | None = None) -> None:
        """Update Hyperion effects."""
        if not self._client.effects:
            return
        effect_list: list[str] = []
        hide_effects = self._get_option(CONF_EFFECT_HIDE_LIST)

        for effect in self._client.effects or []:
            if const.KEY_NAME in effect:
                effect_name = effect[const.KEY_NAME]
                if effect_name not in hide_effects:
                    effect_list.append(effect_name)

        self._effect_list = [
            effect for effect in self._static_effect_list if effect not in hide_effects
        ] + effect_list
        self.async_write_ha_state()

    @callback
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

    @callback
    def _update_client(self, _: dict[str, Any] | None = None) -> None:
        """Update client connection state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ENTITY_REMOVE.format(self.unique_id),
                functools.partial(self.async_remove, force_remove=True),
            )
        )

        self._client.add_callbacks(self._client_callbacks)

        # Load initial state.
        self._update_full_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup prior to hass removal."""
        self._client.remove_callbacks(self._client_callbacks)

    @property
    def _support_external_effects(self) -> bool:
        """Whether or not to support setting external effects from the light entity."""
        return True

    def _get_priority_entry_that_dictates_state(self) -> dict[str, Any] | None:
        """Get the relevant Hyperion priority entry to consider."""
        # Return the visible priority (whether or not it is the HA priority).

        # Explicit type specifier to ensure this works when the underlying (typed)
        # library is installed along with the tests. Casts would trigger a
        # redundant-cast warning in this case.
        priority: dict[str, Any] | None = self._client.visible_priority
        return priority

    # pylint: disable=no-self-use
    def _allow_priority_update(self, priority: dict[str, Any] | None = None) -> bool:
        """Determine whether to allow a priority to update internal state."""
        return True


class HyperionLight(HyperionBaseLight):
    """A Hyperion light that acts in absolute (vs priority) manner.

    Light state is the absolute Hyperion component state (e.g. LED device on/off) rather
    than color based at a particular priority, and the 'winning' priority determines
    shown state rather than exclusively the HA priority.
    """

    def _compute_unique_id(self, server_id: str, instance_num: int) -> str:
        """Compute a unique id for this instance."""
        return get_hyperion_unique_id(server_id, instance_num, TYPE_HYPERION_LIGHT)

    def _compute_name(self, instance_name: str) -> str:
        """Compute the name of the light."""
        return f"{instance_name} {NAME_SUFFIX_HYPERION_LIGHT}".strip()

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return (
            bool(self._client.is_on())
            and self._get_priority_entry_that_dictates_state() is not None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # == Turn device on ==
        # Turn on both ALL (Hyperion itself) and LEDDEVICE. It would be
        # preferable to enable LEDDEVICE after the settings (e.g. brightness,
        # color, effect), but this is not possible due to:
        # https://github.com/hyperion-project/hyperion.ng/issues/967
        if not bool(self._client.is_on()):
            for component in (
                const.KEY_COMPONENTID_ALL,
                const.KEY_COMPONENTID_LEDDEVICE,
            ):
                if not await self._client.async_send_set_component(
                    **{
                        const.KEY_COMPONENTSTATE: {
                            const.KEY_COMPONENT: component,
                            const.KEY_STATE: True,
                        }
                    }
                ):
                    return

        # Turn on the relevant Hyperion priority as usual.
        await super().async_turn_on(**kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        if not await self._client.async_send_set_component(
            **{
                const.KEY_COMPONENTSTATE: {
                    const.KEY_COMPONENT: const.KEY_COMPONENTID_LEDDEVICE,
                    const.KEY_STATE: False,
                }
            }
        ):
            return


class HyperionPriorityLight(HyperionBaseLight):
    """A Hyperion light that only acts on a single Hyperion priority."""

    def _compute_unique_id(self, server_id: str, instance_num: int) -> str:
        """Compute a unique id for this instance."""
        return get_hyperion_unique_id(
            server_id, instance_num, TYPE_HYPERION_PRIORITY_LIGHT
        )

    def _compute_name(self, instance_name: str) -> str:
        """Compute the name of the light."""
        return f"{instance_name} {NAME_SUFFIX_HYPERION_PRIORITY_LIGHT}".strip()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Whether or not the entity is enabled by default."""
        return False

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        priority = self._get_priority_entry_that_dictates_state()
        return (
            priority is not None
            and not HyperionPriorityLight._is_priority_entry_black(priority)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        if not await self._client.async_send_clear(
            **{const.KEY_PRIORITY: self._get_option(CONF_PRIORITY)}
        ):
            return
        await self._client.async_send_set_color(
            **{
                const.KEY_PRIORITY: self._get_option(CONF_PRIORITY),
                const.KEY_COLOR: COLOR_BLACK,
                const.KEY_ORIGIN: DEFAULT_ORIGIN,
            }
        )

    @property
    def _support_external_effects(self) -> bool:
        """Whether or not to support setting external effects from the light entity."""
        return False

    def _get_priority_entry_that_dictates_state(self) -> dict[str, Any] | None:
        """Get the relevant Hyperion priority entry to consider."""
        # Return the active priority (if any) at the configured HA priority.
        for candidate in self._client.priorities or []:
            if const.KEY_PRIORITY not in candidate:
                continue
            if candidate[const.KEY_PRIORITY] == self._get_option(
                CONF_PRIORITY
            ) and candidate.get(const.KEY_ACTIVE, False):
                # Explicit type specifier to ensure this works when the underlying
                # (typed) library is installed along with the tests. Casts would trigger
                # a redundant-cast warning in this case.
                output: dict[str, Any] = candidate
                return output
        return None

    @classmethod
    def _is_priority_entry_black(cls, priority: dict[str, Any] | None) -> bool:
        """Determine if a given priority entry is the color black."""
        if (
            priority
            and priority.get(const.KEY_COMPONENTID) == const.KEY_COMPONENTID_COLOR
        ):
            rgb_color = priority.get(const.KEY_VALUE, {}).get(const.KEY_RGB)
            if rgb_color is not None and tuple(rgb_color) == COLOR_BLACK:
                return True
        return False

    def _allow_priority_update(self, priority: dict[str, Any] | None = None) -> bool:
        """Determine whether to allow a Hyperion priority to update entity attributes."""
        # Black is treated as 'off' (and Home Assistant does not support selecting black
        # from the color selector). Do not set our internal attributes if the priority is
        # 'off' (i.e. if black is active). Do this to ensure it seamlessly turns back on
        # at the correct prior color on the next 'on' call.
        return not HyperionPriorityLight._is_priority_entry_black(priority)


LIGHT_TYPES = {
    TYPE_HYPERION_LIGHT: HyperionLight,
    TYPE_HYPERION_PRIORITY_LIGHT: HyperionPriorityLight,
}
