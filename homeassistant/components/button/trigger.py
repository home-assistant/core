"""Provides triggers for buttons."""

from collections.abc import Collection
from typing import override

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    ButtonEventType,
    EventDeviceClass,
    EventEntityCapabilityAttribute,
    EventEntityStateAttribute,
)
from homeassistant.components.input_button import DOMAIN as INPUT_BUTTON_DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    NotTriggeredReasonReporter,
    StatelessEntityTriggerBase,
    Trigger,
)

from .const import DOMAIN

# Ordered by preference: only the first type an entity declares fires the
# trigger, so a press reported as several of these types fires it once.
PRESSED_EVENT_TYPES: tuple[ButtonEventType, ...] = (
    ButtonEventType.SINGLE_PRESS,
    ButtonEventType.PRESS_END,
    ButtonEventType.PRESS_START,
)


def _get_pressed_event_type(
    event_types: Collection[str] | None,
) -> ButtonEventType | None:
    """Return the event type that fires the pressed trigger, if any."""
    if not event_types:
        return None
    return next((t for t in PRESSED_EVENT_TYPES if t in event_types), None)


class ButtonPressedTrigger(StatelessEntityTriggerBase):
    """Trigger for button presses."""

    _domain_specs = {
        DOMAIN: DomainSpec(),
        INPUT_BUTTON_DOMAIN: DomainSpec(),
        EVENT_DOMAIN: DomainSpec(device_class=EventDeviceClass.BUTTON),
    }

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the state is a button press."""
        if state.domain != EVENT_DOMAIN:
            return True
        event_types = state.attributes.get(EventEntityCapabilityAttribute.EVENT_TYPES)
        if (pressed_event_type := _get_pressed_event_type(event_types)) is None:
            report_not_triggered(
                "entity_event_types_not_supported",
                entity_id=state.entity_id,
                event_types=event_types,
            )
            return False
        return (
            state.attributes.get(EventEntityStateAttribute.EVENT_TYPE)
            == pressed_event_type
        )


TRIGGERS: dict[str, type[Trigger]] = {
    "pressed": ButtonPressedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for buttons."""
    return TRIGGERS
