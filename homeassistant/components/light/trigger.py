"""Provides triggers for lights."""

from typing import TYPE_CHECKING, Final, cast, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.target import (
    TargetStateChangedData,
    async_track_target_selector_state_change_event,
)
from homeassistant.helpers.trigger import Trigger, TriggerActionRunner, TriggerConfig
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

ATTR_BEHAVIOR: Final = "behavior"
BEHAVIOR_FIRST: Final = "first"
BEHAVIOR_LAST: Final = "last"
BEHAVIOR_ANY: Final = "any"

STATE_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
                [BEHAVIOR_FIRST, BEHAVIOR_LAST, BEHAVIOR_ANY]
            ),
        },
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class StateTriggerBase(Trigger):
    """Trigger for state changes."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, STATE_TRIGGER_SCHEMA(config))

    def __init__(
        self, hass: HomeAssistant, config: TriggerConfig, to_state: str
    ) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
            assert config.target is not None
        self._options = config.options
        self._target = config.target
        self._to_state = to_state

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        def check_all_match(entity_ids: set[str]) -> bool:
            """Check if all entity states match."""
            return all(
                state.state == self._to_state
                for entity_id in entity_ids
                if (state := self._hass.states.get(entity_id)) is not None
            )

        def check_one_match(entity_ids: set[str]) -> bool:
            """Check that only one entity state matches."""
            return (
                sum(
                    state.state == self._to_state
                    for entity_id in entity_ids
                    if (state := self._hass.states.get(entity_id)) is not None
                )
                == 1
            )

        behavior = self._options.get(ATTR_BEHAVIOR)

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            # The trigger should never fire if the previous state was not a valid state
            if not from_state or from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                return

            # The trigger should never fire if the new state is not the to state
            if not to_state or to_state.state != self._to_state:
                return

            # The trigger should never fire if the previous and new states are the same
            if from_state.state == to_state.state:
                return

            if behavior == BEHAVIOR_LAST:
                if not check_all_match(target_state_change_data.targeted_entity_ids):
                    return
            elif behavior == BEHAVIOR_FIRST:
                if not check_one_match(target_state_change_data.targeted_entity_ids):
                    return

            run_action(
                {
                    ATTR_ENTITY_ID: entity_id,
                    "from_state": from_state,
                    "to_state": to_state,
                },
                f"state of {entity_id}",
                event.context,
            )

        def entity_filter(entities: set[str]) -> set[str]:
            """Filter entities of this domain."""
            return {
                entity_id
                for entity_id in entities
                if split_entity_id(entity_id)[0] == DOMAIN
            }

        return async_track_target_selector_state_change_event(
            self._hass, self._target, state_change_listener, entity_filter
        )


class TurnedOnTrigger(StateTriggerBase):
    """Trigger for when a light is turned on."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the ON state trigger."""
        super().__init__(hass, config, STATE_ON)


class TurnedOffTrigger(StateTriggerBase):
    """Trigger for when a light is turned off."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the OFF state trigger."""
        super().__init__(hass, config, STATE_OFF)


TRIGGERS: dict[str, type[Trigger]] = {
    "turned_off": TurnedOffTrigger,
    "turned_on": TurnedOnTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for lights."""
    return TRIGGERS
