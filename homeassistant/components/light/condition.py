"""Provides conditions for lights."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final, override

import voluptuous as vol

from homeassistant.const import (
    CONF_OPTIONS,
    CONF_STATE,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import config_validation as cv, target
from homeassistant.helpers.condition import (
    Condition,
    ConditionCheckerType,
    ConditionConfig,
    trace_condition_function,
)
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN

ATTR_BEHAVIOR: Final = "behavior"
BEHAVIOR_ONE: Final = "one"
BEHAVIOR_ANY: Final = "any"
BEHAVIOR_ALL: Final = "all"

STATE_CONDITION_TYPE: Final = "state"

STATE_CONDITION_OPTIONS_SCHEMA: dict[vol.Marker, Any] = {
    vol.Required(CONF_STATE): vol.In([STATE_ON, STATE_OFF]),
    vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
        [BEHAVIOR_ONE, BEHAVIOR_ANY, BEHAVIOR_ALL]
    ),
}
STATE_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
        vol.Required(CONF_OPTIONS): STATE_CONDITION_OPTIONS_SCHEMA,
    }
)


class StateCondition(Condition):
    """State condition."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return STATE_CONDITION_SCHEMA(config)  # type: ignore[no-any-return]

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        self._hass = hass
        if TYPE_CHECKING:
            assert config.target
            assert config.options
        self._target = config.target
        self._state = config.options[CONF_STATE]
        self._behavior = config.options[ATTR_BEHAVIOR]

    @override
    async def async_get_checker(self) -> ConditionCheckerType:
        """Get the condition checker."""

        def check_any_match_state(entity_ids: set[str]) -> bool:
            """Test if any entity match the state."""
            return any(
                entity_state.state == self._state
                for entity_id in entity_ids
                if (entity_state := self._hass.states.get(entity_id))
                is not None  # Ignore unavailable entities
            )

        def check_all_match_state(entity_ids: set[str]) -> bool:
            """Test if all entities match the state."""
            return all(
                entity_state.state == self._state
                for entity_id in entity_ids
                if (entity_state := self._hass.states.get(entity_id))
                is not None  # Ignore unavailable entities
            )

        def check_one_match_state(entity_ids: set[str]) -> bool:
            """Check that only one entity matches the state."""
            matched = False
            for entity_id in entity_ids:
                # Ignore unavailable entities
                if (entity_state := self._hass.states.get(entity_id)) is None:
                    continue
                if entity_state.state != self._state:
                    continue
                if matched:
                    return False
                matched = True
            return matched

        matcher: Callable[[set[str]], bool]
        if self._behavior == BEHAVIOR_ANY:
            matcher = check_any_match_state
        elif self._behavior == BEHAVIOR_ALL:
            matcher = check_all_match_state
        elif self._behavior == BEHAVIOR_ONE:
            matcher = check_one_match_state

        @trace_condition_function
        def test_state(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
            """Test state condition."""
            selector_data = target.TargetSelectorData(self._target)
            targeted_entities = target.async_extract_referenced_entity_ids(
                hass, selector_data, expand_group=False
            )
            referenced_entity_ids = targeted_entities.referenced.union(
                targeted_entities.indirectly_referenced
            )
            light_entity_ids = {
                entity_id
                for entity_id in referenced_entity_ids
                if split_entity_id(entity_id)[0] == DOMAIN
            }
            return matcher(light_entity_ids)

        return test_state


CONDITIONS: dict[str, type[Condition]] = {
    STATE_CONDITION_TYPE: StateCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the light conditions."""
    return CONDITIONS
