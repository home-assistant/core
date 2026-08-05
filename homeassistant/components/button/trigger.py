"""Provides triggers for buttons."""

from typing import override

from homeassistant.components.event import (
    ATTR_MULTI_PRESS_COUNT,
    DOMAIN as EVENT_DOMAIN,
    ButtonEventType,
    EventDeviceClass,
    EventEntityStateAttribute,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    NotTriggeredReasonReporter,
    StatelessEntityTriggerBase,
    Trigger,
)

from . import DOMAIN

_EVENT_BUTTON_DOMAIN_SPECS = {
    EVENT_DOMAIN: DomainSpec(device_class=EventDeviceClass.BUTTON)
}


class ButtonPressedTrigger(StatelessEntityTriggerBase):
    """Trigger for button entity presses."""

    _domain_specs = {
        DOMAIN: DomainSpec(),
        EVENT_DOMAIN: DomainSpec(device_class=EventDeviceClass.BUTTON),
    }

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the state is a button press."""
        if state.domain == EVENT_DOMAIN:
            return (
                state.attributes.get(EventEntityStateAttribute.EVENT_TYPE)
                == ButtonEventType.PRESS_END
            )
        return True


class ButtonDoublePressedTrigger(StatelessEntityTriggerBase):
    """Trigger for button event entity double presses."""

    _domain_specs = _EVENT_BUTTON_DOMAIN_SPECS

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the event is a completed double press."""
        return (
            state.attributes.get(EventEntityStateAttribute.EVENT_TYPE)
            == ButtonEventType.MULTI_PRESS_END
            and state.attributes.get(ATTR_MULTI_PRESS_COUNT) == 2
        )


class ButtonHoldStartedTrigger(StatelessEntityTriggerBase):
    """Trigger for button event entity hold start."""

    _domain_specs = _EVENT_BUTTON_DOMAIN_SPECS

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the event is a hold start."""
        return (
            state.attributes.get(EventEntityStateAttribute.EVENT_TYPE)
            == ButtonEventType.LONG_PRESS_START
        )


class ButtonHoldEndedTrigger(StatelessEntityTriggerBase):
    """Trigger for button event entity hold end."""

    _domain_specs = _EVENT_BUTTON_DOMAIN_SPECS

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the event is a hold end."""
        return (
            state.attributes.get(EventEntityStateAttribute.EVENT_TYPE)
            == ButtonEventType.LONG_PRESS_END
        )


TRIGGERS: dict[str, type[Trigger]] = {
    "pressed": ButtonPressedTrigger,
    "double_pressed": ButtonDoublePressedTrigger,
    "hold_started": ButtonHoldStartedTrigger,
    "hold_ended": ButtonHoldEndedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for buttons."""
    return TRIGGERS
