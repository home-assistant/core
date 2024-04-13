"""Platform for allowing several climate devices to be grouped into one climate device."""

from __future__ import annotations

from statistics import mean
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN,
    PLATFORM_SCHEMA,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntity,
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
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity
from .util import (
    find_state_attributes,
    most_frequent_attribute,
    reduce_attribute,
    states_equal,
)

DEFAULT_NAME = "Climate Group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


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
                hass.config.units.temperature_unit,
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Climate Group config entry."""
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
                hass.config.units.temperature_unit,
            )
        ]
    )


@callback
def async_create_preview_climate(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> ClimateGroup:
    """Create a preview sensor."""
    return ClimateGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
        hass.config.units.temperature_unit,
    )


class ClimateGroup(GroupEntity, ClimateEntity):
    """Representation of a climate group."""

    _attr_available: bool = False
    _attr_assumed_state: bool = True

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        entity_ids: list[str],
        temperature_unit: str,
    ) -> None:
        """Initialize a climate group."""
        self._name = name
        self._entity_ids = entity_ids

        self._features: dict[ClimateEntityFeature, set[str]] = {
            ClimateEntityFeature.TARGET_TEMPERATURE: set(),
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE: set(),
            ClimateEntityFeature.TARGET_HUMIDITY: set(),
            ClimateEntityFeature.FAN_MODE: set(),
            ClimateEntityFeature.PRESET_MODE: set(),
            ClimateEntityFeature.SWING_MODE: set(),
            ClimateEntityFeature.AUX_HEAT: set(),
            ClimateEntityFeature.TURN_ON: set(),
            ClimateEntityFeature.TURN_OFF: set(),
        }

        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}

        self._attr_temperature_unit = temperature_unit

        # Set some defaults (will be overwritten on update)
        self._attr_supported_features: ClimateEntityFeature = ClimateEntityFeature(0)
        self._attr_hvac_modes: list[HVACMode] = [HVACMode.OFF]
        self._attr_hvac_mode: HVACMode | None = None
        self._attr_hvac_action: HVACAction | None = None

        self._attr_swing_modes: list[str] | None = None
        self._attr_swing_mode: str | None = None

        self._attr_fan_modes: list[str] | None = None
        self._attr_fan_mode: str | None = None

        self._attr_preset_modes: list[str] | None = None
        self._attr_preset_mode: str | None = None

    @callback
    def async_update_supported_features(
        self,
        entity_id: str,
        new_state: State | None,
    ) -> None:
        """Update dictionaries with supported features."""
        if not new_state:
            for climate in self._features.values():
                climate.discard(entity_id)
            return

        new_features = new_state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        for feature_flag, entity_set in self._features.items():
            if new_features & feature_flag:
                entity_set.add(entity_id)
            else:
                entity_set.discard(entity_id)

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

        # Temperature settings
        self._attr_target_temperature = reduce_attribute(
            states, ATTR_TEMPERATURE, reduce=lambda *data: mean(data)
        )

        self._attr_target_temperature_step = reduce_attribute(
            states, ATTR_TARGET_TEMP_STEP, reduce=max
        )

        self._attr_target_temperature_low = reduce_attribute(
            states, ATTR_TARGET_TEMP_LOW, reduce=lambda *data: mean(data)
        )
        self._attr_target_temperature_high = reduce_attribute(
            states, ATTR_TARGET_TEMP_HIGH, reduce=lambda *data: mean(data)
        )

        self._attr_current_temperature = reduce_attribute(
            states, ATTR_CURRENT_TEMPERATURE, reduce=lambda *data: mean(data)
        )

        self._attr_min_temp = reduce_attribute(states, ATTR_MIN_TEMP, reduce=max)
        self._attr_max_temp = reduce_attribute(states, ATTR_MAX_TEMP, reduce=min)
        # End temperature settings
        self._attr_target_humidity = reduce_attribute(
            states, ATTR_HUMIDITY, reduce=lambda *data: mean(data)
        )
        self._attr_current_humidity = reduce_attribute(
            states, ATTR_HUMIDITY, reduce=lambda *data: mean(data)
        )
        self._attr_min_humidity = reduce_attribute(
            states, ATTR_MAX_HUMIDITY, reduce=max
        )
        self._attr_max_humidity = reduce_attribute(
            states, ATTR_MIN_HUMIDITY, reduce=min
        )

        # Build util that will help with the computation of union of modes
        # across all the entity states.
        def merge_modes(modes: list[list[Any]]) -> list[Any]:
            return sorted(set().union(*modes))

        # available HVAC modes
        all_hvac_modes = list(find_state_attributes(states, ATTR_HVAC_MODES))
        self._attr_hvac_modes = merge_modes(all_hvac_modes)

        current_hvac_modes = [
            x.state
            for x in states
            if x.state not in [HVACMode.OFF, STATE_UNAVAILABLE, STATE_UNKNOWN]
        ]
        # return the most common hvac mode (what the thermostat is set to do) except OFF, UNKNOWN and UNAVAILABE
        if current_hvac_modes:
            self._attr_hvac_mode = HVACMode(
                max(sorted(set(current_hvac_modes)), key=current_hvac_modes.count)
            )
        # return off if any is off
        elif any(x.state == HVACMode.OFF for x in states):
            self._attr_hvac_mode = HVACMode.OFF
        # else it's none
        else:
            self._attr_hvac_mode = None
        # return the most common action if it is not off
        hvac_actions = list(find_state_attributes(states, ATTR_HVAC_ACTION))
        current_hvac_actions = [a for a in hvac_actions if a != HVACAction.OFF]
        # return the most common action if it is not off
        if current_hvac_actions:
            self._attr_hvac_action = max(
                sorted(set(current_hvac_actions)), key=current_hvac_actions.count
            )
        # return action off if all are off
        elif all(a == HVACAction.OFF for a in hvac_actions):
            self._attr_hvac_action = HVACAction.OFF
        # else it's none
        else:
            self._attr_hvac_action = None

        # available swing modes
        all_swing_modes = list(find_state_attributes(states, ATTR_SWING_MODES))
        self._attr_swing_modes = merge_modes(all_swing_modes)

        # Report the most common swing_mode.
        self._attr_swing_mode = most_frequent_attribute(states, ATTR_SWING_MODE)

        # available fan modes
        all_fan_modes = list(find_state_attributes(states, ATTR_FAN_MODES))
        self._attr_fan_modes = merge_modes(all_fan_modes)

        # Report the most common fan_mode.
        self._attr_fan_mode = most_frequent_attribute(states, ATTR_FAN_MODE)

        # available preset modes
        all_preset_modes = list(find_state_attributes(states, ATTR_PRESET_MODES))
        self._attr_preset_modes = merge_modes(all_preset_modes)

        # Report the most common fan_mode.
        self._attr_preset_mode = most_frequent_attribute(states, ATTR_PRESET_MODE)

        # Bitwise-and the supported features with the Grouped climate's features
        # so that we don't break in the future when a new feature is added.
        self._attr_supported_features = ClimateEntityFeature(0)
        for feature_flags, entities in self._features.items():
            if not entities:
                continue
            self._attr_supported_features |= feature_flags

    async def _async_set_temperature_values(
        self,
        *,
        temp: float,
        temp_low: float,
        temp_high: float,
        hvac_mode: HVACMode | None = None,
    ) -> None:
        data: dict[str, Any] = {}
        if hvac_mode is not None:
            data |= {
                ATTR_HVAC_MODE: hvac_mode,
            }

        # Call for entities only supporting setting temperature value.
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            data
            | {
                ATTR_ENTITY_ID: self._features[ClimateEntityFeature.TARGET_TEMPERATURE]
                - self._features[ClimateEntityFeature.TARGET_TEMPERATURE_RANGE],
                ATTR_TEMPERATURE: temp,
            },
            context=self._context,
        )
        # Call for entities only supporting setting temperature range.
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            data
            | {
                ATTR_ENTITY_ID: self._features[
                    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                ]
                - self._features[ClimateEntityFeature.TARGET_TEMPERATURE],
                ATTR_TARGET_TEMP_HIGH: temp_high,
                ATTR_TARGET_TEMP_LOW: temp_low,
            },
            context=self._context,
        )
        # Call for entities supporting both temperature value and range.
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            data
            | {
                ATTR_ENTITY_ID: self._features[ClimateEntityFeature.TARGET_TEMPERATURE]
                | self._features[ClimateEntityFeature.TARGET_TEMPERATURE_RANGE],
                ATTR_TEMPERATURE: temp,
                ATTR_TARGET_TEMP_HIGH: temp_high,
                ATTR_TARGET_TEMP_LOW: temp_low,
            },
            context=self._context,
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Forward the temperature command to all climate in the climate group."""
        if temp := kwargs.get(ATTR_TEMPERATURE):
            await self._async_set_temperature_values(
                temp=temp,
                temp_high=temp,
                temp_low=temp,
                hvac_mode=kwargs.get(ATTR_HVAC_MODE),
            )
        elif (temp_high := kwargs.get(ATTR_TARGET_TEMP_HIGH)) and (
            temp_low := kwargs.get(ATTR_TARGET_TEMP_LOW)
        ):
            await self._async_set_temperature_values(
                temp=(temp_high + temp_low) / 2.0,
                temp_high=temp_high,
                temp_low=temp_low,
                hvac_mode=kwargs.get(ATTR_HVAC_MODE),
            )

    async def async_set_humidity(self, humidity: int) -> None:
        """Forward the humidity to all supported climate in the climate group."""
        data = {
            ATTR_ENTITY_ID: self._features[ClimateEntityFeature.TARGET_HUMIDITY],
            ATTR_HUMIDITY: humidity,
        }
        await self.hass.services.async_call(
            DOMAIN, SERVICE_SET_HUMIDITY, data, context=self._context
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Forward the HVAC mode all climate in the climate group."""
        data = {ATTR_ENTITY_ID: self._entity_ids, ATTR_HVAC_MODE: hvac_mode}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_SET_HVAC_MODE, data, context=self._context
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Forward the fan_mode to all climate in the climate group."""
        data = {
            ATTR_ENTITY_ID: self._features[ClimateEntityFeature.FAN_MODE],
            ATTR_FAN_MODE: fan_mode,
        }
        await self.hass.services.async_call(
            DOMAIN, SERVICE_SET_FAN_MODE, data, context=self._context
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Forward the swing_mode to all climate in the climate group."""
        data = {
            ATTR_ENTITY_ID: self._features[ClimateEntityFeature.SWING_MODE],
            ATTR_SWING_MODE: swing_mode,
        }
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SWING_MODE,
            data,
            context=self._context,
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Forward the preset_mode to all climate in the climate group."""
        data = {
            ATTR_ENTITY_ID: self._features[ClimateEntityFeature.PRESET_MODE],
            ATTR_PRESET_MODE: preset_mode,
        }
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            data,
            blocking=True,
            context=self._context,
        )
