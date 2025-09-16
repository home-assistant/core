"""Provides conditions for lights."""

from typing import Final, override

import voluptuous as vol

from homeassistant.const import (
    CONF_CONDITION,
    CONF_STATE,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import config_validation as cv, selector, target
from homeassistant.helpers.condition import (
    Condition,
    ConditionCheckerType,
    trace_condition_function,
)
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN

# remove when #151314 is merged
CONF_OPTIONS: Final = "options"

ATTR_BEHAVIOR: Final = "behavior"
BEHAVIOR_ONE: Final = "one"
BEHAVIOR_ANY: Final = "any"
BEHAVIOR_ALL: Final = "all"

STATE_CONDITION_TYPE: Final = "state"
STATE_CONDITION_SCHEMA = vol.Schema(
    {
        **cv.CONDITION_BASE_SCHEMA,
        vol.Required(CONF_CONDITION): f"{DOMAIN}.{STATE_CONDITION_TYPE}",
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_STATE): vol.In([STATE_ON, STATE_OFF]),
            vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
                [BEHAVIOR_ONE, BEHAVIOR_ANY, BEHAVIOR_ALL]
            ),
        },
        vol.Required(CONF_TARGET): selector.TargetSelector.TARGET_SELECTION_SCHEMA,
    },
)


class StateCondition(Condition):
    """State condition."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize condition."""
        self._hass = hass
        self._config = config

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return STATE_CONDITION_SCHEMA(config)  # type: ignore[no-any-return]

    @override
    async def async_get_checker(self) -> ConditionCheckerType:
        """Wrap action method with zone based condition."""
        options_config = self._config[CONF_OPTIONS]
        state = options_config[CONF_STATE]
        behavior = options_config[ATTR_BEHAVIOR]

        def check_any_match_state(entity_ids: set[str]) -> bool:
            """Test if any entity match the state."""
            return any(
                entity_state.state == state
                for entity_id in entity_ids
                if (entity_state := self._hass.states.get(entity_id))
                is not None  # Ignore unavailable entities
            )

        def check_all_match_state(entity_ids: set[str]) -> bool:
            """Test if all entities match the state."""
            return all(
                entity_state.state == state
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
                if entity_state.state != state:
                    continue
                if matched:
                    return False
                matched = True
            return matched

        if behavior == BEHAVIOR_ANY:
            matcher = check_any_match_state
        elif behavior == BEHAVIOR_ALL:
            matcher = check_all_match_state
        elif behavior == BEHAVIOR_ONE:
            matcher = check_one_match_state

        target_config = self._config.get(CONF_TARGET, {})

        @trace_condition_function
        def test_state(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
            """Test state condition."""
            selector_data = target.TargetSelectorData(target_config)
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
