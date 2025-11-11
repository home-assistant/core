"""Provides triggers for media players."""

from typing import TYPE_CHECKING, cast, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_OFF,
    STATE_UNAVAILABLE,
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

TURNS_ON_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default={}): {},
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class MediaPlayerTurnsOnTrigger(Trigger):
    """Trigger for when a media player turns on."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, TURNS_ON_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the media player turns on trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
        self._target = config.target

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

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

            # Trigger when turning on from off state
            if (
                from_state is not None
                and from_state.state == STATE_OFF
                and to_state.state != STATE_OFF
            ):
                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                    },
                    f"media player {entity_id} turned on",
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


TRIGGERS: dict[str, type[Trigger]] = {
    "turns_on": MediaPlayerTurnsOnTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for media players."""
    return TRIGGERS
