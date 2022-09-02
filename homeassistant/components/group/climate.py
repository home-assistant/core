"""This platform allows several climate devices to be grouped into one climate device."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import DOMAIN, PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_TEMPERATURE_UNIT,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import GroupEntity
from .util import (
    find_state_attributes,
    most_frequent_attribute,
    reduce_attribute,
    states_equal,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Climate Group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_TEMPERATURE_UNIT, default=TEMP_CELSIUS): cv.string,
        vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
    }
)
# edit the supported_flags
SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.SWING_MODE
    | ClimateEntityFeature.FAN_MODE
)


# HVAC Action priority
HVAC_ACTIONS_PRIORITY = [
    HVACAction.HEATING,
    HVACAction.COOLING,
    HVACAction.DRYING,
    HVACAction.FAN,
    HVACAction.IDLE,
    HVACAction.OFF,
    None,
]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Initialize climate.group platform."""
    async_add_entities(
        [
            ClimateGroup(
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                config[CONF_ENTITIES],
                config[CONF_TEMPERATURE_UNIT],
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Light Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )

    async_add_entities(
        [
            ClimateGroup(
                config_entry.entry_id,
                config_entry.title,
                entities,
                config_entry.options[CONF_TEMPERATURE_UNIT],
            )
        ]
    )


class ClimateGroup(GroupEntity, ClimateEntity):
    """Representation of a climate group."""

    _attr_available: bool = False
    _attr_assumed_state: bool = True

    def __init__(
        self, unique_id: str | None, name: str, entity_ids: list[str], unit: str
    ) -> None:
        """Initialize a climate group."""
        self._entity_ids = entity_ids

        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}

        if "c" in unit.lower():
            self._attr_temperature_unit = TEMP_CELSIUS
        else:
            self._attr_temperature_unit = TEMP_FAHRENHEIT

        # Set some defaults (will be overwritten on update)
        self._attr_supported_features = 0
        self._attr_hvac_modes = [HVACMode.OFF]
        self._attr_hvac_mode = None
        self._attr_hvac_action = None

        self._attr_swing_modes = None
        self._attr_swing_mode = None

        self._attr_fan_modes = None
        self._attr_fan_mode = None

        self._attr_preset_modes = None
        self._attr_preset_mode = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def async_state_changed_listener(event: Event) -> None:
            """Handle child updates."""
            self.async_set_context(event.context)
            self.async_defer_or_update_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_ids, async_state_changed_listener
            )
        )

        await super().async_added_to_hass()

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the climate group state."""
        self._attr_assumed_state = False

        states = [
            state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]
        self._attr_assumed_state |= not states_equal(states)

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)

        def _mean(*args: float) -> float:
            """Return the mean of the supplied values."""
            return sum(args) / len(args)

        # Temperature settings
        self._attr_target_temperature = reduce_attribute(
            states, ATTR_TEMPERATURE, reduce=_mean
        )

        self._attr_target_temperature_step = reduce_attribute(
            states, ATTR_TARGET_TEMP_STEP, reduce=max
        )

        self._attr_target_temperature_low = reduce_attribute(
            states, ATTR_TARGET_TEMP_LOW, reduce=_mean
        )
        self._attr_target_temperature_high = reduce_attribute(
            states, ATTR_TARGET_TEMP_HIGH, reduce=_mean
        )

        self._attr_current_temperature = reduce_attribute(
            states, ATTR_CURRENT_TEMPERATURE, reduce=_mean
        )

        self._attr_min_temp = reduce_attribute(states, ATTR_MIN_TEMP, reduce=max)
        self._attr_max_temp = reduce_attribute(states, ATTR_MAX_TEMP, reduce=min)
        # End temperature settings

        # available HVAC modes
        all_hvac_modes = list(find_state_attributes(states, ATTR_HVAC_MODES))
        if all_hvac_modes:
            # Merge all effects from all effect_lists with a union merge.
            self._attr_hvac_modes = list(set().union(*all_hvac_modes))

        current_hvac_modes = [x.state for x in states]
        # return the hvac mode (what the thermostat is set to do) in priority order (heat, cool, ...)
        # iterate through all hvac modes (skip first, as its off)
        for hvac_mode in list(HVACMode)[1:] + [HVACMode.OFF]:
            # if any thermostat is in the given mode return it
            if any(mode == hvac_mode for mode in current_hvac_modes):
                self._attr_hvac_mode = hvac_mode
                break

        current_hvac_actions = list(find_state_attributes(states, ATTR_HVAC_ACTION))
        for hvac_action in HVAC_ACTIONS_PRIORITY:
            # if any thermostat is in the given action return it
            if any(action == hvac_action for action in current_hvac_actions):
                self._attr_hvac_action = hvac_action
                break

        # available swing modes
        all_swing_modes = list(find_state_attributes(states, ATTR_SWING_MODES))
        if all_swing_modes:
            self._attr_swing_modes = list(set().union(*all_swing_modes))

        # Report the most common swing_mode.
        self._attr_swing_mode = most_frequent_attribute(states, ATTR_SWING_MODE)

        # available fan modes
        all_fan_modes = list(find_state_attributes(states, ATTR_FAN_MODES))
        if all_fan_modes:
            # Merge all effects from all effect_lists with a union merge.
            self._attr_fan_modes = list(set().union(*all_fan_modes))

        # Report the most common fan_mode.
        self._attr_fan_mode = most_frequent_attribute(states, ATTR_FAN_MODE)

        # available preset modes
        all_preset_modes = list(find_state_attributes(states, ATTR_PRESET_MODES))
        if all_preset_modes:
            # Merge all effects from all effect_lists with a union merge.
            self._attr_preset_modes = list(set().union(*all_preset_modes))

        # Report the most common fan_mode.
        self._attr_preset_mode = most_frequent_attribute(states, ATTR_PRESET_MODE)

        # Supported flags
        for support in find_state_attributes(states, ATTR_SUPPORTED_FEATURES):
            # Merge supported features by emulating support for every feature
            # we find.
            self._attr_supported_features |= support

        # Bitwise-and the supported features with the Grouped climate's features
        # so that we don't break in the future when a new feature is added.
        self._attr_supported_features &= SUPPORT_FLAGS

        _LOGGER.debug("State update complete")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Forward the turn_on command to all climate in the climate group."""
        data = {ATTR_ENTITY_ID: self._entity_ids}

        if ATTR_HVAC_MODE in kwargs:
            _LOGGER.debug("Set temperature with HVAC MODE")
            await self.async_set_hvac_mode(kwargs[ATTR_HVAC_MODE])

        if ATTR_TEMPERATURE in kwargs:
            data["target_temperature"] = kwargs[ATTR_TEMPERATURE]
        if ATTR_TARGET_TEMP_LOW in kwargs:
            data["target_temperature_low"] = kwargs[ATTR_TARGET_TEMP_LOW]
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            data["target_temperature_high"] = kwargs[ATTR_TARGET_TEMP_HIGH]

        _LOGGER.debug("Setting temperature: %s", data)

        await self.hass.services.async_call(
            DOMAIN, SERVICE_SET_TEMPERATURE, data, blocking=True, context=self._context
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Forward the turn_on command to all climate in the climate group."""
        data = {ATTR_ENTITY_ID: self._entity_ids, ATTR_HVAC_MODE: hvac_mode}
        _LOGGER.debug("Setting hvac mode: %s", data)
        await self.hass.services.async_call(
            DOMAIN, SERVICE_SET_HVAC_MODE, data, blocking=True, context=self._context
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Forward the fan_mode to all climate in the climate group."""
        data = {ATTR_ENTITY_ID: self._entity_ids, ATTR_FAN_MODE: fan_mode}
        _LOGGER.debug("Setting fan mode: %s", data)
        await self.hass.services.async_call(
            DOMAIN, SERVICE_SET_FAN_MODE, data, blocking=True, context=self._context
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Forward the swing_mode to all climate in the climate group."""
        data = {ATTR_ENTITY_ID: self._entity_ids, ATTR_SWING_MODE: swing_mode}
        _LOGGER.debug("Setting swing mode: %s", data)
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SWING_MODE,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Forward the preset_mode to all climate in the climate group."""
        data = {ATTR_ENTITY_ID: self._entity_ids, ATTR_PRESET_MODE: preset_mode}
        _LOGGER.debug("Setting preset mode: %s", data)
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            data,
            blocking=True,
            context=self._context,
        )
