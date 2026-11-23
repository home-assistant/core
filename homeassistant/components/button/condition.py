"""Provides conditions for buttons."""

from typing import override

import probatio

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    ButtonEventType,
    EventDeviceClass,
    EventEntityCapabilityAttribute,
    EventEntityStateAttribute,
)
from homeassistant.const import CONF_FOR, CONF_OPTIONS
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL,
    Condition,
    EntityConditionBase,
)
from homeassistant.util import dt as dt_util

from .const import HOLD_TIMEOUT

IS_BEING_HELD_CONDITION_SCHEMA = ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL.extend(
    {
        probatio.Required(CONF_OPTIONS, default={}): {
            # A hold times out, so a longer duration could never pass.
            probatio.Optional(CONF_FOR): probatio.All(
                cv.positive_time_period,
                probatio.Range(max=HOLD_TIMEOUT, max_included=False),
            ),
        },
    }
)


class ButtonIsBeingHeldCondition(EntityConditionBase):
    """Condition for buttons being held."""

    _domain_specs = {EVENT_DOMAIN: DomainSpec(device_class=EventDeviceClass.BUTTON)}
    _schema = IS_BEING_HELD_CONDITION_SCHEMA

    @property
    @override
    def _needs_duration_tracking(self) -> bool:
        """Return if this condition needs duration tracking.

        The state is the timestamp of the last event, so it changes on every event.
        While held, the last event is long_press_start, so last_changed is no earlier
        than when the hold started.
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
            # Like the held trigger, so a missed release doesn't keep it held. Uses
            # the earlier time: restores and availability changes set last_changed,
            # and a clock going back puts the event time in the future.
            and (event_time := dt_util.parse_datetime(entity_state.state)) is not None
            and dt_util.utcnow() - min(event_time, entity_state.last_changed)
            < HOLD_TIMEOUT
        )


CONDITIONS: dict[str, type[Condition]] = {
    "is_being_held": ButtonIsBeingHeldCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for buttons."""
    return CONDITIONS
