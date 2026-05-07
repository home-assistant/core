"""Provides triggers for doorbells."""

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    DOMAIN as EVENT_DOMAIN,
    DoorbellEventType,
    EventDeviceClass,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import StatelessEntityTriggerBase, Trigger


class DoorbellRangTrigger(StatelessEntityTriggerBase):
    """Trigger for doorbell event entity when a ring event is received."""

    _domain_specs = {EVENT_DOMAIN: DomainSpec(device_class=EventDeviceClass.DOORBELL)}

    def is_valid_state(self, state: State) -> bool:
        """Check if the event type is ring."""
        return state.attributes.get(ATTR_EVENT_TYPE) == DoorbellEventType.RING


TRIGGERS: dict[str, type[Trigger]] = {
    "rang": DoorbellRangTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for doorbells."""
    return TRIGGERS
