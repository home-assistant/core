"""Provides triggers for lights."""

from typing import cast, override

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM, CONF_STATE, MATCH_ALL
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import process_state_match
from homeassistant.helpers.target import async_track_target_selector_state_change_event
from homeassistant.helpers.trigger import Trigger, TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

STATE_PLATFORM_TYPE = f"{DOMAIN}.state"
STATE_TRIGGER_SCHEMA = vol.All(
    cv.TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_PLATFORM): STATE_PLATFORM_TYPE,
            vol.Optional(CONF_STATE, default=MATCH_ALL): vol.Any(str, [str], None),
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

        match_state = process_state_match(self.config.get(CONF_STATE))

        @callback
        def state_change_listener(event: Event[EventStateChangedData]) -> None:
            """Listen for state changes and call action."""
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            if to_state is None:
                return
            if not match_state(to_state.state):
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
