"""This platform allows several lights to be grouped into one light."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
import itertools
from typing import Any, Callable, Set, cast

import voluptuous as vol

from homeassistant.components import light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    ATTR_XY_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_ONOFF,
    PLATFORM_SCHEMA,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_NAME,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CoreState, Event, HomeAssistant, State
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

from . import GroupEntity

DEFAULT_NAME = "Light Group"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_ENTITIES): cv.entities_domain(light.DOMAIN),
    }
)

SUPPORT_GROUP_LIGHT = (
    SUPPORT_EFFECT | SUPPORT_FLASH | SUPPORT_TRANSITION | SUPPORT_WHITE_VALUE
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Initialize light.group platform."""
    async_add_entities(
        [LightGroup(cast(str, config.get(CONF_NAME)), config[CONF_ENTITIES])]
    )


class LightGroup(GroupEntity, light.LightEntity):
    """Representation of a light group."""

    _attr_available = False
    _attr_icon = "mdi:lightbulb-group"
    _attr_is_on = False
    _attr_max_mireds = 500
    _attr_min_mireds = 154
    _attr_should_poll = False

    def __init__(self, name: str, entity_ids: list[str]) -> None:
        """Initialize a light group."""
        self._entity_ids = entity_ids
        self._white_value: int | None = None

        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        async def async_state_changed_listener(event: Event) -> None:
            """Handle child updates."""
            self.async_set_context(event.context)
            await self.async_defer_or_update_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_ids, async_state_changed_listener
            )
        )

        if self.hass.state == CoreState.running:
            await self.async_update()
            return

        await super().async_added_to_hass()

    @property
    def white_value(self) -> int | None:
        """Return the white value of this light group between 0..255."""
        return self._white_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command to all lights in the light group."""
        data = {ATTR_ENTITY_ID: self._entity_ids}

        if ATTR_BRIGHTNESS in kwargs:
            data[ATTR_BRIGHTNESS] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_HS_COLOR in kwargs:
            data[ATTR_HS_COLOR] = kwargs[ATTR_HS_COLOR]

        if ATTR_RGB_COLOR in kwargs:
            data[ATTR_RGB_COLOR] = kwargs[ATTR_RGB_COLOR]

        if ATTR_RGBW_COLOR in kwargs:
            data[ATTR_RGBW_COLOR] = kwargs[ATTR_RGBW_COLOR]

        if ATTR_RGBWW_COLOR in kwargs:
            data[ATTR_RGBWW_COLOR] = kwargs[ATTR_RGBWW_COLOR]

        if ATTR_XY_COLOR in kwargs:
            data[ATTR_XY_COLOR] = kwargs[ATTR_XY_COLOR]

        if ATTR_COLOR_TEMP in kwargs:
            data[ATTR_COLOR_TEMP] = kwargs[ATTR_COLOR_TEMP]

        if ATTR_WHITE_VALUE in kwargs:
            data[ATTR_WHITE_VALUE] = kwargs[ATTR_WHITE_VALUE]

        if ATTR_EFFECT in kwargs:
            data[ATTR_EFFECT] = kwargs[ATTR_EFFECT]

        if ATTR_TRANSITION in kwargs:
            data[ATTR_TRANSITION] = kwargs[ATTR_TRANSITION]

        if ATTR_FLASH in kwargs:
            data[ATTR_FLASH] = kwargs[ATTR_FLASH]

        await self.hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_ON,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward the turn_off command to all lights in the light group."""
        data = {ATTR_ENTITY_ID: self._entity_ids}

        if ATTR_TRANSITION in kwargs:
            data[ATTR_TRANSITION] = kwargs[ATTR_TRANSITION]

        await self.hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_OFF,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_update(self) -> None:
        """Query all members and determine the light group state."""
        all_states = [self.hass.states.get(x) for x in self._entity_ids]
        states: list[State] = list(filter(None, all_states))
        on_states = [state for state in states if state.state == STATE_ON]

        self._attr_is_on = len(on_states) > 0
        self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)
        self._attr_brightness = _reduce_attribute(on_states, ATTR_BRIGHTNESS)

        self._attr_hs_color = _reduce_attribute(
            on_states, ATTR_HS_COLOR, reduce=_mean_tuple
        )
        self._attr_rgb_color = _reduce_attribute(
            on_states, ATTR_RGB_COLOR, reduce=_mean_tuple
        )
        self._attr_rgbw_color = _reduce_attribute(
            on_states, ATTR_RGBW_COLOR, reduce=_mean_tuple
        )
        self._attr_rgbww_color = _reduce_attribute(
            on_states, ATTR_RGBWW_COLOR, reduce=_mean_tuple
        )
        self._attr_xy_color = _reduce_attribute(
            on_states, ATTR_XY_COLOR, reduce=_mean_tuple
        )

        self._white_value = _reduce_attribute(on_states, ATTR_WHITE_VALUE)

        self._attr_color_temp = _reduce_attribute(on_states, ATTR_COLOR_TEMP)
        self._attr_min_mireds = _reduce_attribute(
            states, ATTR_MIN_MIREDS, default=154, reduce=min
        )
        self._attr_max_mireds = _reduce_attribute(
            states, ATTR_MAX_MIREDS, default=500, reduce=max
        )

        self._attr_effect_list = None
        all_effect_lists = list(_find_state_attributes(states, ATTR_EFFECT_LIST))
        if all_effect_lists:
            # Merge all effects from all effect_lists with a union merge.
            self._attr_effect_list = list(set().union(*all_effect_lists))
            self._attr_effect_list.sort()
            if "None" in self._attr_effect_list:
                self._attr_effect_list.remove("None")
                self._attr_effect_list.insert(0, "None")

        self._attr_effect = None
        all_effects = list(_find_state_attributes(on_states, ATTR_EFFECT))
        if all_effects:
            # Report the most common effect.
            effects_count = Counter(itertools.chain(all_effects))
            self._attr_effect = effects_count.most_common(1)[0][0]

        self._attr_color_mode = None
        all_color_modes = list(_find_state_attributes(on_states, ATTR_COLOR_MODE))
        if all_color_modes:
            # Report the most common color mode, select brightness and onoff last
            color_mode_count = Counter(itertools.chain(all_color_modes))
            if COLOR_MODE_ONOFF in color_mode_count:
                color_mode_count[COLOR_MODE_ONOFF] = -1
            if COLOR_MODE_BRIGHTNESS in color_mode_count:
                color_mode_count[COLOR_MODE_BRIGHTNESS] = 0
            self._attr_color_mode = color_mode_count.most_common(1)[0][0]

        self._attr_supported_color_modes = None
        all_supported_color_modes = list(
            _find_state_attributes(states, ATTR_SUPPORTED_COLOR_MODES)
        )
        if all_supported_color_modes:
            # Merge all color modes.
            self._attr_supported_color_modes = cast(
                Set[str], set().union(*all_supported_color_modes)
            )

        self._attr_supported_features = 0
        for support in _find_state_attributes(states, ATTR_SUPPORTED_FEATURES):
            # Merge supported features by emulating support for every feature
            # we find.
            self._attr_supported_features |= support
        # Bitwise-and the supported features with the GroupedLight's features
        # so that we don't break in the future when a new feature is added.
        self._attr_supported_features &= SUPPORT_GROUP_LIGHT


def _find_state_attributes(states: list[State], key: str) -> Iterator[Any]:
    """Find attributes with matching key from states."""
    for state in states:
        value = state.attributes.get(key)
        if value is not None:
            yield value


def _mean_int(*args: Any) -> int:
    """Return the mean of the supplied values."""
    return int(sum(args) / len(args))


def _mean_tuple(*args: Any) -> tuple[float | Any, ...]:
    """Return the mean values along the columns of the supplied values."""
    return tuple(sum(x) / len(x) for x in zip(*args))


def _reduce_attribute(
    states: list[State],
    key: str,
    default: Any | None = None,
    reduce: Callable[..., Any] = _mean_int,
) -> Any:
    """Find the first attribute matching key from states.

    If none are found, return default.
    """
    attrs = list(_find_state_attributes(states, key))

    if not attrs:
        return default

    if len(attrs) == 1:
        return attrs[0]

    return reduce(*attrs)
