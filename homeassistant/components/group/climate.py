"""Platform allowing several climate entities to be grouped into one climate entity."""

from collections import Counter
from collections.abc import Iterable
from enum import StrEnum
from functools import reduce
from operator import ior
from typing import Any, override

import probatio

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityCapabilityAttribute,
    ClimateEntityFeature,
    ClimateEntityStateAttribute,
    ClimateService,
    ClimateServiceArgument,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    PRECISION_TENTHS,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import GroupEntityStateAttribute
from .entity import GroupEntity
from .util import find_state_attributes, reduce_attribute

SUPPORTED_FLAGS = {
    ClimateEntityFeature.TARGET_TEMPERATURE,
    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
    ClimateEntityFeature.TARGET_HUMIDITY,
    ClimateEntityFeature.FAN_MODE,
    ClimateEntityFeature.PRESET_MODE,
    ClimateEntityFeature.SWING_MODE,
    ClimateEntityFeature.SWING_HORIZONTAL_MODE,
    ClimateEntityFeature.TURN_OFF,
    ClimateEntityFeature.TURN_ON,
}

# Highest priority first, the group reports the first mode or action any member has
HVAC_MODE_PRIORITY = [
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.HEAT_COOL,
    HVACMode.AUTO,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
    HVACMode.OFF,
]
HVAC_ACTION_PRIORITY = [
    HVACAction.HEATING,
    HVACAction.PREHEATING,
    HVACAction.DEFROSTING,
    HVACAction.COOLING,
    HVACAction.DRYING,
    HVACAction.FAN,
    HVACAction.IDLE,
    HVACAction.OFF,
]

DEFAULT_NAME = "Climate Group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_ENTITIES): cv.entities_domain(CLIMATE_DOMAIN),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Climate Group platform."""
    async_add_entities(
        [
            ClimateGroup(
                config.get(CONF_UNIQUE_ID), config[CONF_NAME], config[CONF_ENTITIES]
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Climate Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )

    async_add_entities(
        [ClimateGroup(config_entry.entry_id, config_entry.title, entities)]
    )


@callback
def async_create_preview_climate(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> ClimateGroup:
    """Create a preview climate."""
    return ClimateGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
    )


def _union_of_lists(states: list[State], key: str) -> list[Any]:
    """Return the union of list attributes, keeping the order they are first seen."""
    return list(
        dict.fromkeys(
            item for values in find_state_attributes(states, key) for item in values
        )
    )


def _mean(*args: float) -> float:
    """Return the mean of the supplied values."""
    return sum(args) / len(args)


def _most_frequent_attribute(states: list[State], key: str) -> Any | None:
    """Return the most frequent attribute value, the first member wins a tie."""
    if counts := Counter(find_state_attributes(states, key)).most_common(1):
        return counts[0][0]
    return None


def _highest_priority[T: StrEnum](values: Iterable[str], priority: list[T]) -> T | None:
    """Return the value with the highest priority."""
    present = set(values)
    return next((value for value in priority if value in present), None)


class ClimateGroup(GroupEntity, ClimateEntity):
    """Representation of a ClimateGroup."""

    _attr_available: bool = False
    _attr_hvac_mode: HVACMode | None = None
    _attr_precision = PRECISION_TENTHS

    def __init__(self, unique_id: str | None, name: str, entities: list[str]) -> None:
        """Initialize a ClimateGroup entity."""
        self._entity_ids = entities
        self._climates: dict[int, set[str]] = {flag: set() for flag in SUPPORTED_FLAGS}
        self._attr_name = name
        self._attr_extra_state_attributes = {
            GroupEntityStateAttribute.ENTITY_ID: entities
        }
        self._attr_unique_id = unique_id
        self._attr_hvac_modes = []

    @property
    @override
    def native_temperature_unit(self) -> str:
        """Return the unit of measurement, members report in the system unit."""
        return self.hass.config.units.temperature_unit

    @callback
    @override
    def async_update_supported_features(
        self,
        entity_id: str,
        new_state: State | None,
    ) -> None:
        """Update dictionaries with supported features."""
        if not new_state:
            for values in self._climates.values():
                values.discard(entity_id)
        else:
            features = new_state.attributes.get(
                EntityStateAttribute.SUPPORTED_FEATURES, 0
            )
            for feature in SUPPORTED_FLAGS:
                if features & feature:
                    self._climates[feature].add(entity_id)
                else:
                    self._climates[feature].discard(entity_id)

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        # Members handle hvac_mode differently in set_temperature, set it separately
        if (
            hvac_mode := kwargs.pop(ClimateServiceArgument.HVAC_MODE, None)
        ) is not None:
            await self.async_set_hvac_mode(hvac_mode)
        if ClimateServiceArgument.TEMPERATURE in kwargs:
            await self._async_call_supported_entities(
                ClimateService.SET_TEMPERATURE,
                self._climates[ClimateEntityFeature.TARGET_TEMPERATURE],
                {
                    ClimateServiceArgument.TEMPERATURE: kwargs[
                        ClimateServiceArgument.TEMPERATURE
                    ]
                },
            )
        if ClimateServiceArgument.TARGET_TEMP_LOW in kwargs:
            await self._async_call_supported_entities(
                ClimateService.SET_TEMPERATURE,
                self._climates[ClimateEntityFeature.TARGET_TEMPERATURE_RANGE],
                {
                    ClimateServiceArgument.TARGET_TEMP_LOW: kwargs[
                        ClimateServiceArgument.TARGET_TEMP_LOW
                    ],
                    ClimateServiceArgument.TARGET_TEMP_HIGH: kwargs[
                        ClimateServiceArgument.TARGET_TEMP_HIGH
                    ],
                },
            )

    @override
    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self._async_call_supported_entities(
            ClimateService.SET_HUMIDITY,
            self._climates[ClimateEntityFeature.TARGET_HUMIDITY],
            {ClimateServiceArgument.HUMIDITY: humidity},
        )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._async_call_supported_entities(
            ClimateService.SET_HVAC_MODE,
            self._entities_with_mode(
                self._entity_ids, ClimateEntityCapabilityAttribute.HVAC_MODES, hvac_mode
            ),
            {ClimateServiceArgument.HVAC_MODE: hvac_mode},
        )

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._async_call_supported_entities(
            ClimateService.SET_FAN_MODE,
            self._entities_with_mode(
                self._climates[ClimateEntityFeature.FAN_MODE],
                ClimateEntityCapabilityAttribute.FAN_MODES,
                fan_mode,
            ),
            {ClimateServiceArgument.FAN_MODE: fan_mode},
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        await self._async_call_supported_entities(
            ClimateService.SET_PRESET_MODE,
            self._entities_with_mode(
                self._climates[ClimateEntityFeature.PRESET_MODE],
                ClimateEntityCapabilityAttribute.PRESET_MODES,
                preset_mode,
            ),
            {ClimateServiceArgument.PRESET_MODE: preset_mode},
        )

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        await self._async_call_supported_entities(
            ClimateService.SET_SWING_MODE,
            self._entities_with_mode(
                self._climates[ClimateEntityFeature.SWING_MODE],
                ClimateEntityCapabilityAttribute.SWING_MODES,
                swing_mode,
            ),
            {ClimateServiceArgument.SWING_MODE: swing_mode},
        )

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new target horizontal swing mode."""
        await self._async_call_supported_entities(
            ClimateService.SET_SWING_HORIZONTAL_MODE,
            self._entities_with_mode(
                self._climates[ClimateEntityFeature.SWING_HORIZONTAL_MODE],
                ClimateEntityCapabilityAttribute.SWING_HORIZONTAL_MODES,
                swing_horizontal_mode,
            ),
            {ClimateServiceArgument.SWING_HORIZONTAL_MODE: swing_horizontal_mode},
        )

    @override
    async def async_turn_on(self) -> None:
        """Turn the entities on."""
        # Members which are already on could otherwise be switched to another mode
        await self._async_call_supported_entities(
            SERVICE_TURN_ON,
            [
                entity_id
                for entity_id in self._climates[ClimateEntityFeature.TURN_ON]
                if (state := self.hass.states.get(entity_id)) is not None
                and state.state == HVACMode.OFF
            ],
            {},
        )

    @override
    async def async_turn_off(self) -> None:
        """Turn the entities off."""
        await self._async_call_supported_entities(
            SERVICE_TURN_OFF, self._climates[ClimateEntityFeature.TURN_OFF], {}
        )

    def _entities_with_mode(
        self, entity_ids: list[str] | set[str], modes_attr: str, mode: str
    ) -> list[str]:
        """Return the entities which list the mode as one of their modes."""
        return [
            entity_id
            for entity_id in entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
            and mode in (state.attributes.get(modes_attr) or [])
        ]

    async def _async_call_supported_entities(
        self, service: str, entity_ids: list[str] | set[str], data: dict[str, Any]
    ) -> None:
        """Call a service with the given entities."""
        await self.hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {**data, ATTR_ENTITY_ID: entity_ids},
            blocking=True,
            context=self._context,
        )

    def _async_states_by_support_flag(self, flag: int) -> list[State]:
        """Return all the entity states for a supported flag, in member order."""
        return [
            state
            for entity_id in self._entity_ids
            if entity_id in self._climates[flag]
            and (state := self.hass.states.get(entity_id)) is not None
        ]

    @callback
    @override
    def async_update_group_state(self) -> None:
        """Update state and attributes."""
        self._update_assumed_state_from_members()

        states = [
            state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]
        valid_states = [
            state
            for state in states
            if state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ]

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)

        self._attr_hvac_mode = _highest_priority(
            (state.state for state in valid_states), HVAC_MODE_PRIORITY
        )
        self._attr_hvac_action = _highest_priority(
            find_state_attributes(
                valid_states, ClimateEntityStateAttribute.HVAC_ACTION
            ),
            HVAC_ACTION_PRIORITY,
        )
        self._attr_hvac_modes = _union_of_lists(
            states, ClimateEntityCapabilityAttribute.HVAC_MODES
        )

        self._attr_native_current_temperature = reduce_attribute(
            states, ClimateEntityStateAttribute.CURRENT_TEMPERATURE, reduce=_mean
        )
        self._attr_current_humidity = reduce_attribute(
            states, ClimateEntityStateAttribute.CURRENT_HUMIDITY, reduce=_mean
        )

        temperature_states = self._async_states_by_support_flag(
            ClimateEntityFeature.TARGET_TEMPERATURE
        )
        range_states = self._async_states_by_support_flag(
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        )
        self._attr_native_target_temperature = reduce_attribute(
            temperature_states,
            ClimateEntityStateAttribute.TARGET_TEMPERATURE,
            reduce=_mean,
        )
        self._attr_native_target_temperature_low = reduce_attribute(
            range_states, ClimateEntityStateAttribute.TARGET_TEMP_LOW, reduce=_mean
        )
        self._attr_native_target_temperature_high = reduce_attribute(
            range_states, ClimateEntityStateAttribute.TARGET_TEMP_HIGH, reduce=_mean
        )

        # Members reject values outside their own range, so use the overlapping range
        temperature_setting_states = temperature_states + range_states
        if (
            min_temp := reduce_attribute(
                temperature_setting_states,
                ClimateEntityCapabilityAttribute.MIN_TEMP,
                reduce=max,
            )
        ) is not None:
            self._attr_min_temp = min_temp
        if (
            max_temp := reduce_attribute(
                temperature_setting_states,
                ClimateEntityCapabilityAttribute.MAX_TEMP,
                reduce=min,
            )
        ) is not None:
            self._attr_max_temp = max_temp
        self._attr_target_temperature_step = reduce_attribute(
            temperature_setting_states,
            ClimateEntityCapabilityAttribute.TARGET_TEMP_STEP,
            reduce=max,
        )

        humidity_states = self._async_states_by_support_flag(
            ClimateEntityFeature.TARGET_HUMIDITY
        )
        self._attr_target_humidity = reduce_attribute(
            humidity_states, ClimateEntityStateAttribute.TARGET_HUMIDITY, reduce=_mean
        )
        if (
            min_humidity := reduce_attribute(
                humidity_states,
                ClimateEntityCapabilityAttribute.MIN_HUMIDITY,
                reduce=max,
            )
        ) is not None:
            self._attr_min_humidity = min_humidity
        if (
            max_humidity := reduce_attribute(
                humidity_states,
                ClimateEntityCapabilityAttribute.MAX_HUMIDITY,
                reduce=min,
            )
        ) is not None:
            self._attr_max_humidity = max_humidity
        self._attr_target_humidity_step = reduce_attribute(
            humidity_states,
            ClimateEntityCapabilityAttribute.TARGET_HUMIDITY_STEP,
            reduce=max,
        )

        for flag, mode_attr, modes_attr in (
            (
                ClimateEntityFeature.FAN_MODE,
                ClimateEntityStateAttribute.FAN_MODE,
                ClimateEntityCapabilityAttribute.FAN_MODES,
            ),
            (
                ClimateEntityFeature.PRESET_MODE,
                ClimateEntityStateAttribute.PRESET_MODE,
                ClimateEntityCapabilityAttribute.PRESET_MODES,
            ),
            (
                ClimateEntityFeature.SWING_MODE,
                ClimateEntityStateAttribute.SWING_MODE,
                ClimateEntityCapabilityAttribute.SWING_MODES,
            ),
            (
                ClimateEntityFeature.SWING_HORIZONTAL_MODE,
                ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE,
                ClimateEntityCapabilityAttribute.SWING_HORIZONTAL_MODES,
            ),
        ):
            mode_states = self._async_states_by_support_flag(flag)
            setattr(
                self,
                f"_attr_{mode_attr}",
                _most_frequent_attribute(mode_states, mode_attr),
            )
            setattr(
                self, f"_attr_{modes_attr}", _union_of_lists(mode_states, modes_attr)
            )

        self._attr_supported_features = ClimateEntityFeature(
            reduce(
                ior,
                [feature for feature in SUPPORTED_FLAGS if self._climates[feature]],
                0,
            )
        )
