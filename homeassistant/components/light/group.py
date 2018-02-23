"""
This component allows several lights to be grouped into one light.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.group/
"""
import asyncio
import logging
import itertools
from typing import List, Tuple, Optional, Iterator, Any, Callable
from collections import Counter
from copy import deepcopy

import voluptuous as vol

from homeassistant.core import State, callback
from homeassistant.components import light
from homeassistant.const import (STATE_OFF, STATE_ON, SERVICE_TURN_ON,
                                 SERVICE_TURN_OFF, ATTR_ENTITY_ID, CONF_NAME,
                                 CONF_ENTITIES, STATE_UNAVAILABLE,
                                 STATE_UNKNOWN, ATTR_SUPPORTED_FEATURES)
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.components.light import (
    SUPPORT_BRIGHTNESS, SUPPORT_RGB_COLOR, SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION, SUPPORT_EFFECT, SUPPORT_FLASH, SUPPORT_XY_COLOR,
    SUPPORT_WHITE_VALUE, PLATFORM_SCHEMA, ATTR_BRIGHTNESS, ATTR_XY_COLOR,
    ATTR_RGB_COLOR, ATTR_WHITE_VALUE, ATTR_COLOR_TEMP, ATTR_MIN_MIREDS,
    ATTR_MAX_MIREDS, ATTR_EFFECT_LIST, ATTR_EFFECT)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'group'

DEFAULT_NAME = 'Group Light'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_ENTITIES): cv.entity_ids,
})

SUPPORT_GROUP_LIGHT = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_EFFECT
                       | SUPPORT_FLASH | SUPPORT_RGB_COLOR | SUPPORT_TRANSITION
                       | SUPPORT_XY_COLOR | SUPPORT_WHITE_VALUE)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_devices, discovery_info=None) -> None:
    """Initialize light.group platform."""
    async_add_devices(
        [GroupLight(hass, config.get(CONF_NAME), config[CONF_ENTITIES])], True)


class GroupLight(light.Light):
    """Representation of a group light."""

    def __init__(self, hass: HomeAssistantType, name: str,
                 entity_ids: List[str]) -> None:
        """Initialize a group light."""
        self.hass = hass  # type: HomeAssistantType
        self._name = name  # type: str
        self._entity_ids = entity_ids  # type: List[str]
        self._state = STATE_UNAVAILABLE  # type: str
        self._brightness = None  # type: Optional[int]
        self._xy_color = None  # type: Optional[Tuple[float, float]]
        self._rgb_color = None  # type: Optional[Tuple[int, int, int]]
        self._color_temp = None  # type: Optional[int]
        self._min_mireds = 154  # type: Optional[int]
        self._max_mireds = 500  # type: Optional[int]
        self._white_value = None  # type: Optional[int]
        self._effect_list = None  # type: Optional[List[str]]
        self._effect = None  # type: Optional[str]
        self._supported_features = 0  # type: int
        self._async_unsub_state_changed = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        @callback
        def async_state_changed_listener(entity_id: str, old_state: State,
                                         new_state: State):
            """Handle child updates."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_state_changed = async_track_state_change(
            self.hass, self._entity_ids, async_state_changed_listener)

    async def async_will_remove_from_hass(self):
        """Callback when removed from HASS."""
        if self._async_unsub_state_changed:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state."""
        return self._state

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._state == STATE_ON

    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def xy_color(self) -> Optional[Tuple[float, float]]:
        """Return the XY color value [float, float]."""
        return self._xy_color

    @property
    def rgb_color(self) -> Optional[Tuple[int, int, int]]:
        """Return the RGB color value [int, int, int]."""
        return self._rgb_color

    @property
    def color_temp(self) -> Optional[int]:
        """Return the CT color value in mireds."""
        return self._color_temp

    @property
    def min_mireds(self) -> Optional[int]:
        """Return the coldest color_temp that this light supports."""
        return self._min_mireds

    @property
    def max_mireds(self) -> Optional[int]:
        """Return the warmest color_temp that this light supports."""
        return self._max_mireds

    @property
    def white_value(self) -> Optional[int]:
        """Return the white value of this light between 0..255."""
        return self._white_value

    @property
    def effect_list(self) -> Optional[List[str]]:
        """Return the list of supported effects."""
        return self._effect_list

    @property
    def effect(self) -> Optional[str]:
        """Return the current effect."""
        return self._effect

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def should_poll(self) -> bool:
        """No polling needed for a group light."""
        return False

    async def _async_send_message(self, service, **kwargs):
        """Send a message to all entities in the group."""
        tasks = []
        for entity_id in self._entity_ids:
            payload = deepcopy(kwargs)
            payload[ATTR_ENTITY_ID] = entity_id
            tasks.append(self.hass.services.async_call(
                light.DOMAIN, service, payload, blocking=True))

        if tasks:
            await asyncio.wait(tasks, loop=self.hass.loop)

    async def async_turn_on(self, **kwargs):
        """Forward the turn_on command to all lights in the group."""
        await self._async_send_message(SERVICE_TURN_ON, **kwargs)

    async def async_turn_off(self, **kwargs):
        """Forward the turn_off command to all lights in the group."""
        await self._async_send_message(SERVICE_TURN_OFF, **kwargs)

    async def async_update(self):
        """Query all members and determine the group state."""
        states = self._child_states()
        on_states = [state for state in states if state.state == STATE_ON]

        self._state = _determine_on_off_state(states)

        self._brightness = _reduce_attribute(on_states, ATTR_BRIGHTNESS)

        self._xy_color = _reduce_attribute(
            on_states, ATTR_XY_COLOR, reduce=_average_tuple)

        self._rgb_color = _reduce_attribute(
            on_states, ATTR_RGB_COLOR, reduce=_average_tuple)
        if self._rgb_color is not None:
            self._rgb_color = tuple(map(int, self._rgb_color))

        self._white_value = _reduce_attribute(on_states, ATTR_WHITE_VALUE)

        self._color_temp = _reduce_attribute(on_states, ATTR_COLOR_TEMP)
        self._min_mireds = _reduce_attribute(
            states, ATTR_MIN_MIREDS, default=154, reduce=min)
        self._max_mireds = _reduce_attribute(
            states, ATTR_MAX_MIREDS, default=500, reduce=max)

        self._effect_list = None
        all_effect_lists = list(
            _find_state_attributes(states, ATTR_EFFECT_LIST))
        if all_effect_lists:
            # Merge all effects from all effect_lists with a union merge.
            self._effect_list = list(set().union(*all_effect_lists))

        self._effect = None
        all_effects = list(_find_state_attributes(on_states, ATTR_EFFECT))
        if all_effects:
            # Report the most common effect.
            effects_count = Counter(itertools.chain(all_effects))
            self._effect = effects_count.most_common(1)[0][0]

        self._supported_features = 0
        for support in _find_state_attributes(states, ATTR_SUPPORTED_FEATURES):
            # Merge supported features by emulating support for every feature
            # we find.
            self._supported_features |= support
        # Bitwise-and the supported features with the GroupedLight's features
        # so that we don't break in the future when a new feature is added.
        self._supported_features &= SUPPORT_GROUP_LIGHT

    def _child_states(self) -> List[State]:
        """The states that the group is tracking."""
        states = [self.hass.states.get(x) for x in self._entity_ids]
        return list(filter(None, states))


def _find_state_attributes(states: List[State],
                           key: str) -> Iterator[Any]:
    """Find attributes with matching key from states."""
    for state in states:
        value = state.attributes.get(key)
        if value is not None:
            yield value


def _average_int(*args):
    """Return the average of the supplied values."""
    return int(sum(args) / len(args))


def _average_tuple(*args):
    """Return the average values along the columns of the supplied values."""
    return tuple(sum(l) / len(l) for l in zip(*args))


# https://github.com/PyCQA/pylint/issues/1831
# pylint: disable=bad-whitespace
def _reduce_attribute(states: List[State],
                      key: str,
                      default: Optional[Any] = None,
                      reduce: Callable[..., Any] = _average_int) -> Any:
    """Find the first attribute matching key from states.

    If none are found, return default.
    """
    attrs = list(_find_state_attributes(states, key))

    if not attrs:
        return default

    if len(attrs) == 1:
        return attrs[0]

    return reduce(*attrs)


def _determine_on_off_state(states: List[State]) -> str:
    """Helper method to determine the ON/OFF/... state of a light."""
    s_states = [state.state for state in states]

    if not s_states or all(state == STATE_UNAVAILABLE for state in s_states):
        return STATE_UNAVAILABLE
    elif any(state == STATE_ON for state in s_states):
        return STATE_ON
    elif all(state == STATE_UNKNOWN for state in s_states):
        return STATE_UNKNOWN
    return STATE_OFF
