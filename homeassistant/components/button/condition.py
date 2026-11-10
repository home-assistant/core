"""Provides conditions for buttons."""

from typing import override

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    ButtonEventType,
    EventDeviceClass,
    EventEntityCapabilityAttribute,
    EventEntityStateAttribute,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import Condition, EntityConditionBase
from homeassistant.util import dt as dt_util

from .const import HOLD_TIMEOUT


class ButtonIsBeingHeldCondition(EntityConditionBase):
    """Condition for buttons being held."""

    _domain_specs = {EVENT_DOMAIN: DomainSpec(device_class=EventDeviceClass.BUTTON)}

    @property
    @override
    def _needs_duration_tracking(self) -> bool:
        """Return if this condition needs duration tracking.

        The state is the timestamp of the last event, so it changes on every event.
        While held, the last event is long_press_start, so last_changed is when the
        hold started.
        """
        return False

    @property
    @override
    def needs_polling(self) -> bool:
        """Return True, as a hold times out without a state change."""
        return True

    @override
    def _should_include(self, state: State) -> bool:
        """Skip entities that can't tell when a hold ends."""
        event_types = (
            state.attributes.get(EventEntityCapabilityAttribute.EVENT_TYPES) or ()
        )
        # Requires both, to know the button is held while it is down.
        return (
            super()._should_include(state)
            and ButtonEventType.LONG_PRESS_START in event_types
            and ButtonEventType.LONG_PRESS_END in event_types
        )

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the last event of the entity started a hold, not timed out."""
        return (
            entity_state.attributes.get(EventEntityStateAttribute.EVENT_TYPE)
            == ButtonEventType.LONG_PRESS_START
            # Like the held trigger, so a missed release doesn't keep it held.
            and dt_util.utcnow() - entity_state.last_changed < HOLD_TIMEOUT
        )


CONDITIONS: dict[str, type[Condition]] = {
    "is_being_held": ButtonIsBeingHeldCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for buttons."""
    return CONDITIONS
