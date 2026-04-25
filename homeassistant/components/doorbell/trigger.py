"""Provides triggers for doorbells."""

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    DOMAIN as EVENT_DOMAIN,
    DoorbellEventType,
    EventDeviceClass,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    Trigger,
)


class DoorbellRangTrigger(EntityTriggerBase):
    """Trigger for doorbell event entity when a ring event is received."""

    _domain_specs = {EVENT_DOMAIN: DomainSpec(device_class=EventDeviceClass.DOORBELL)}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_state(self, state: State) -> bool:
        """Check if the entity is available and the event type is ring."""
        return (
            state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            and state.attributes.get(ATTR_EVENT_TYPE) == DoorbellEventType.RING
        )

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and different from the current state."""

        # UNKNOWN is a valid from_state, otherwise the first time the event is received
        # would not trigger
        if from_state.state == STATE_UNAVAILABLE:
            return False

        return from_state.state != to_state.state


TRIGGERS: dict[str, type[Trigger]] = {
    "rang": DoorbellRangTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for doorbells."""
    return TRIGGERS
