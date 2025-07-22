"""Provides triggers for lights."""

from typing import Final, cast, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    CONF_STATE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import process_state_match
from homeassistant.helpers.target import (
    TargetStateChangedData,
    async_track_target_selector_state_change_event,
)
from homeassistant.helpers.trigger import Trigger, TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

ATTR_BEHAVIOR: Final = "behavior"
BEHAVIOR_FIRST = "first"
BEHAVIOR_LAST = "last"
BEHAVIOR_ANY = "any"

STATE_PLATFORM_TYPE = f"{DOMAIN}.state"
STATE_TRIGGER_SCHEMA = vol.All(
    cv.TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_PLATFORM): STATE_PLATFORM_TYPE,
            vol.Required(CONF_STATE): vol.In([STATE_ON, STATE_OFF]),
            vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
                [BEHAVIOR_FIRST, BEHAVIOR_LAST, BEHAVIOR_ANY]
            ),
            **cv.ENTITY_SERVICE_FIELDS,
        },
    ),
    cv.has_at_least_one_key(*cv.ENTITY_SERVICE_FIELDS),
)


class StateTrigger(Trigger):
    """Trigger for state changes."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize the state trigger."""
        self.hass = hass
        self.config = config

    @override
    @classmethod
    async def async_validate_trigger_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, STATE_TRIGGER_SCHEMA(config))

    @override
    async def async_attach_trigger(
        self,
        action: TriggerActionType,
        trigger_info: TriggerInfo,
    ) -> CALLBACK_TYPE:
        """Attach the trigger."""
        job = HassJob(action, f"light state trigger {trigger_info}")
        trigger_data = trigger_info["trigger_data"]

        behavior = self.config.get(ATTR_BEHAVIOR)
        match_config_state = process_state_match(self.config.get(CONF_STATE))

        def check_all_match(entity_ids: set[str]) -> bool:
            """Check if all entity states match."""
            return all(
                match_config_state(state.state)
                for entity_id in entity_ids
                if (state := self.hass.states.get(entity_id)) is not None
            )

        def check_one_match(entity_ids: set[str]) -> bool:
            """Check that only one entity state matches."""
            return (
                sum(
                    match_config_state(state.state)
                    for entity_id in entity_ids
                    if (state := self.hass.states.get(entity_id)) is not None
                )
                == 1
            )

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            if to_state is None:
                return

            # This check is required for "first" behavior, to check that it went from zero
            # entities matching the state to one. Otherwise, if previously there were two
            # entities on CONF_STATE and one changed, this would trigger.
            # For "last" behavior it is not required, but serves as a quicker fail check.
            if not match_config_state(to_state.state):
                return
            if behavior == BEHAVIOR_LAST:
                if not check_all_match(target_state_change_data.targeted_entity_ids):
                    return
            elif behavior == BEHAVIOR_FIRST:
                if not check_one_match(target_state_change_data.targeted_entity_ids):
                    return

            self.hass.async_run_hass_job(
                job,
                {
                    "trigger": {
                        **trigger_data,
                        CONF_PLATFORM: STATE_PLATFORM_TYPE,
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                        "description": f"state of {entity_id}",
                    }
                },
                event.context,
            )

        return async_track_target_selector_state_change_event(
            self.hass, self.config, state_change_listener
        )


TRIGGERS: dict[str, type[Trigger]] = {
    STATE_PLATFORM_TYPE: StateTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for lights."""
    return TRIGGERS
