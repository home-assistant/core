"""Provides conditions for lights."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final, Unpack, override

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS, CONF_TARGET, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import config_validation as cv, target
from homeassistant.helpers.condition import (
    Condition,
    ConditionChecker,
    ConditionCheckParams,
    ConditionConfig,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

ATTR_BEHAVIOR: Final = "behavior"
BEHAVIOR_ANY: Final = "any"
BEHAVIOR_ALL: Final = "all"


STATE_CONDITION_VALID_STATES: Final = [STATE_ON, STATE_OFF]
STATE_CONDITION_OPTIONS_SCHEMA: dict[vol.Marker, Any] = {
    vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
        [BEHAVIOR_ANY, BEHAVIOR_ALL]
    ),
}
STATE_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
        vol.Required(CONF_OPTIONS): STATE_CONDITION_OPTIONS_SCHEMA,
    }
)


class StateConditionBase(Condition):
    """State condition."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return STATE_CONDITION_SCHEMA(config)  # type: ignore[no-any-return]

    def __init__(
        self, hass: HomeAssistant, config: ConditionConfig, state: str
    ) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target
            assert config.options
        self._target = config.target
        self._behavior = config.options[ATTR_BEHAVIOR]
        self._state = state

    @override
    async def async_get_checker(self) -> ConditionChecker:
        """Get the condition checker."""

        def check_any_match_state(states: list[str]) -> bool:
            """Test if any entity match the state."""
            return any(state == self._state for state in states)

        def check_all_match_state(states: list[str]) -> bool:
            """Test if all entities match the state."""
            return all(state == self._state for state in states)

        matcher: Callable[[list[str]], bool]
        if self._behavior == BEHAVIOR_ANY:
            matcher = check_any_match_state
        elif self._behavior == BEHAVIOR_ALL:
            matcher = check_all_match_state

        def test_state(**kwargs: Unpack[ConditionCheckParams]) -> bool:
            """Test state condition."""
            target_selection = target.TargetSelection(self._target)
            targeted_entities = target.async_extract_referenced_entity_ids(
                self._hass, target_selection, expand_group=False
            )
            referenced_entity_ids = targeted_entities.referenced.union(
                targeted_entities.indirectly_referenced
            )
            light_entity_ids = {
                entity_id
                for entity_id in referenced_entity_ids
                if split_entity_id(entity_id)[0] == DOMAIN
            }
            light_entity_states = [
                state.state
                for entity_id in light_entity_ids
                if (state := self._hass.states.get(entity_id))
                and state.state in STATE_CONDITION_VALID_STATES
            ]
            return matcher(light_entity_states)

        return test_state


class IsOnCondition(StateConditionBase):
    """Is on condition."""

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config, STATE_ON)


class IsOffCondition(StateConditionBase):
    """Is off condition."""

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config, STATE_OFF)


CONDITIONS: dict[str, type[Condition]] = {
    "is_off": IsOffCondition,
    "is_on": IsOnCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the light conditions."""
    return CONDITIONS
