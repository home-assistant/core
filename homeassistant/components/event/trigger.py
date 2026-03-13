"""Provides triggers for events."""

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    Trigger,
    TriggerConfig,
)

from .const import ATTR_EVENT_TYPE, DOMAIN

CONF_EVENT_TYPE = "event_type"

EVENT_RECEIVED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_EVENT_TYPE): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        },
    }
)


class EventReceivedTrigger(EntityTriggerBase):
    """Trigger for event entity when it receives a matching event."""

    _domains = {DOMAIN}
    _schema = EVENT_RECEIVED_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the event received trigger."""
        super().__init__(hass, config)
        self._event_types = set(self._options[CONF_EVENT_TYPE])

    def is_valid_state(self, state: State) -> bool:
        """Check if the event type matches one of the configured types."""
        return state.attributes.get(ATTR_EVENT_TYPE) in self._event_types


TRIGGERS: dict[str, type[Trigger]] = {
    "received": EventReceivedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for events."""
    return TRIGGERS
