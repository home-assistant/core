"""Platform allowing several lights to be grouped into one light."""

from __future__ import annotations

from collections import Counter
import itertools
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_WHITE,
    ATTR_XY_COLOR,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    filter_supported_color_modes,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity
from .util import find_state_attributes, mean_tuple, reduce_attribute

DEFAULT_NAME = "Light Group"
CONF_ALL = "all"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Required(CONF_ENTITIES): cv.entities_domain(light.DOMAIN),
        vol.Optional(CONF_ALL): cv.boolean,
    }
)

SUPPORT_GROUP_LIGHT = (
    LightEntityFeature.EFFECT | LightEntityFeature.FLASH | LightEntityFeature.TRANSITION
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Initialize light.group platform."""
    async_add_entities(
        [
            LightGroup(
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                config[CONF_ENTITIES],
                config.get(CONF_ALL),
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Light Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )
    mode = config_entry.options.get(CONF_ALL, False)

    async_add_entities(
        [LightGroup(config_entry.entry_id, config_entry.title, entities, mode)]
    )


@callback
def async_create_preview_light(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> LightGroup:
    """Create a preview sensor."""
    return LightGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
        validated_config.get(CONF_ALL, False),
    )


FORWARDED_ATTRIBUTES = frozenset(
    {
        ATTR_BRIGHTNESS,
        ATTR_COLOR_TEMP_KELVIN,
        ATTR_EFFECT,
        ATTR_FLASH,
        ATTR_HS_COLOR,
        ATTR_RGB_COLOR,
        ATTR_RGBW_COLOR,
        ATTR_RGBWW_COLOR,
        ATTR_TRANSITION,
        ATTR_WHITE,
        ATTR_XY_COLOR,
    }
)


class LightGroup(GroupEntity, LightEntity):
    """Representation of a light group."""

    _attr_available = False
    _attr_icon = "mdi:lightbulb-group"
    _attr_max_color_temp_kelvin = 6500
    _attr_min_color_temp_kelvin = 2000
    _attr_should_poll = False

    def __init__(
        self, unique_id: str | None, name: str, entity_ids: list[str], mode: bool | None
    ) -> None:
        """Initialize a light group."""
        self._entity_ids = entity_ids

        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}
        self._attr_unique_id = unique_id
        self.mode = any
        if mode:
            self.mode = all

        self._attr_color_mode = ColorMode.UNKNOWN
        self._attr_supported_color_modes = {ColorMode.ONOFF}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command to all lights in the light group."""
        data = {
            key: value for key, value in kwargs.items() if key in FORWARDED_ATTRIBUTES
        }
        data[ATTR_ENTITY_ID] = self._entity_ids

        _LOGGER.debug("Forwarded turn_on command: %s", data)

        await self.hass.services.async_call(
            light.DOMAIN,
            SERVICE_TURN_ON,
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
            SERVICE_TURN_OFF,
            data,
            blocking=True,
            context=self._context,
        )

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the light group state."""
        states = [
            state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]
        on_states = [state for state in states if state.state == STATE_ON]

        valid_state = self.mode(
            state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )

        if not valid_state:
            # Set as unknown if any / all member is unknown or unavailable
            self._attr_is_on = None
        else:
            # Set as ON if any / all member is ON
            self._attr_is_on = self.mode(state.state == STATE_ON for state in states)

        self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)
        self._attr_brightness = reduce_attribute(on_states, ATTR_BRIGHTNESS)

        self._attr_hs_color = reduce_attribute(
            on_states, ATTR_HS_COLOR, reduce=mean_tuple
        )
        self._attr_rgb_color = reduce_attribute(
            on_states, ATTR_RGB_COLOR, reduce=mean_tuple
        )
        self._attr_rgbw_color = reduce_attribute(
            on_states, ATTR_RGBW_COLOR, reduce=mean_tuple
        )
        self._attr_rgbww_color = reduce_attribute(
            on_states, ATTR_RGBWW_COLOR, reduce=mean_tuple
        )
        self._attr_xy_color = reduce_attribute(
            on_states, ATTR_XY_COLOR, reduce=mean_tuple
        )

        self._attr_color_temp_kelvin = reduce_attribute(
            on_states, ATTR_COLOR_TEMP_KELVIN
        )
        self._attr_min_color_temp_kelvin = reduce_attribute(
            states, ATTR_MIN_COLOR_TEMP_KELVIN, default=2000, reduce=min
        )
        self._attr_max_color_temp_kelvin = reduce_attribute(
            states, ATTR_MAX_COLOR_TEMP_KELVIN, default=6500, reduce=max
        )

        self._attr_effect_list = None
        all_effect_lists = list(find_state_attributes(states, ATTR_EFFECT_LIST))
        if all_effect_lists:
            # Merge all effects from all effect_lists with a union merge.
            self._attr_effect_list = list(set().union(*all_effect_lists))
            self._attr_effect_list.sort()
            if "None" in self._attr_effect_list:
                self._attr_effect_list.remove("None")
                self._attr_effect_list.insert(0, "None")

        self._attr_effect = None
        all_effects = list(find_state_attributes(on_states, ATTR_EFFECT))
        if all_effects:
            # Report the most common effect.
            effects_count = Counter(itertools.chain(all_effects))
            self._attr_effect = effects_count.most_common(1)[0][0]

        supported_color_modes = {ColorMode.ONOFF}
        all_supported_color_modes = list(
            find_state_attributes(states, ATTR_SUPPORTED_COLOR_MODES)
        )
        if all_supported_color_modes:
            # Merge all color modes.
            supported_color_modes = filter_supported_color_modes(
                cast(set[ColorMode], set().union(*all_supported_color_modes))
            )
        self._attr_supported_color_modes = supported_color_modes

        self._attr_color_mode = ColorMode.UNKNOWN
        all_color_modes = list(find_state_attributes(on_states, ATTR_COLOR_MODE))
        if all_color_modes:
            # Report the most common color mode, select brightness and onoff last
            color_mode_count = Counter(itertools.chain(all_color_modes))
            if ColorMode.ONOFF in color_mode_count:
                if ColorMode.ONOFF in supported_color_modes:
                    color_mode_count[ColorMode.ONOFF] = -1
                else:
                    color_mode_count.pop(ColorMode.ONOFF)
            if ColorMode.BRIGHTNESS in color_mode_count:
                if ColorMode.BRIGHTNESS in supported_color_modes:
                    color_mode_count[ColorMode.BRIGHTNESS] = 0
                else:
                    color_mode_count.pop(ColorMode.BRIGHTNESS)
            if color_mode_count:
                self._attr_color_mode = color_mode_count.most_common(1)[0][0]
            else:
                self._attr_color_mode = next(iter(supported_color_modes))

        self._attr_supported_features = LightEntityFeature(0)
        for support in find_state_attributes(states, ATTR_SUPPORTED_FEATURES):
            # Merge supported features by emulating support for every feature
            # we find.
            self._attr_supported_features |= support
        # Bitwise-and the supported features with the GroupedLight's features
        # so that we don't break in the future when a new feature is added.
        self._attr_supported_features &= SUPPORT_GROUP_LIGHT
