"""Provides triggers for assist satellites."""

from typing import TYPE_CHECKING, cast, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_TARGET,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import process_state_match
from homeassistant.helpers.target import (
    TargetStateChangedData,
    async_track_target_selector_state_change_event,
)
from homeassistant.helpers.trigger import Trigger, TriggerActionRunner, TriggerConfig
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

STATE_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class StateTriggerBase(Trigger):
    """Trigger for assist satellite state changes."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, STATE_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig, state: str) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
        self._target = config.target
        self._state = state

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        match_config_state = process_state_match(self._state)

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            # Ignore unavailable states
            if to_state is None or to_state.state == STATE_UNAVAILABLE:
                return

            # Check if the new state matches the trigger state
            if not match_config_state(to_state.state):
                return

            run_action(
                {
                    ATTR_ENTITY_ID: entity_id,
                    "from_state": from_state,
                    "to_state": to_state,
                },
                f"{entity_id} {self._state}",
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


class ListeningTrigger(StateTriggerBase):
    """Trigger for when a satellite starts listening."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the listening trigger."""
        super().__init__(hass, config, "listening")


class ProcessingTrigger(StateTriggerBase):
    """Trigger for when a satellite starts processing."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the processing trigger."""
        super().__init__(hass, config, "processing")


TRIGGERS: dict[str, type[Trigger]] = {
    "listening": ListeningTrigger,
    "processing": ProcessingTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for assist satellites."""
    return TRIGGERS
