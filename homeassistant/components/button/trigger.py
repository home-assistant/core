"""Provides triggers for buttons."""

from collections.abc import Collection, Mapping
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, override

import probatio

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    ButtonEventType,
    EventDeviceClass,
    EventEntityCapabilityAttribute,
    EventEntityStateAttribute,
)
from homeassistant.components.input_button import DOMAIN as INPUT_BUTTON_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_OPTIONS
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.target import (
    TargetStateChangedData,
    async_track_target_selector_state_change_event,
)
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    NotTriggeredInfo,
    NotTriggeredReasonReporter,
    StatelessEntityTriggerBase,
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)

from .const import DOMAIN

ATTR_REPEAT_COUNT: Final = "repeat_count"
CONF_INTERVAL: Final = "interval"

HOLD_TIMEOUT: Final = timedelta(seconds=30)

# Ordered by preference: only the first type an entity declares fires the
# trigger, so a press reported as several of these types fires it once.
PRESSED_EVENT_TYPES: tuple[ButtonEventType, ...] = (
    ButtonEventType.SINGLE_PRESS,
    ButtonEventType.PRESS_END,
    ButtonEventType.PRESS_START,
)
# Ordered by preference: only the first type an entity declares fires the
# trigger.
HELD_EVENT_TYPES: tuple[ButtonEventType, ...] = (
    ButtonEventType.LONG_PRESS_START,
    ButtonEventType.LONG_PRESS_END,
)

HELD_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA.extend(
    {
        probatio.Required(CONF_OPTIONS, default={}): {
            probatio.Optional(CONF_INTERVAL): probatio.All(
                cv.time_period,
                probatio.Range(
                    min=timedelta(0),
                    min_included=False,
                    max=HOLD_TIMEOUT,
                    max_included=False,
                ),
            ),
        },
    }
)


def _get_first_declared_event_type(
    event_types: Collection[str] | None,
    candidates: tuple[ButtonEventType, ...],
) -> ButtonEventType | None:
    """Return the first of the candidate event types the entity declares."""
    if not event_types:
        return None
    return next((t for t in candidates if t in event_types), None)


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
        if (
            pressed_event_type := _get_first_declared_event_type(
                event_types, PRESSED_EVENT_TYPES
            )
        ) is None:
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


class ButtonHeldTrigger(StatelessEntityTriggerBase):
    """Trigger for button holds, optionally repeating while held."""

    _domain_specs = {EVENT_DOMAIN: DomainSpec(device_class=EventDeviceClass.BUTTON)}
    _schema = HELD_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the held trigger."""
        super().__init__(hass, config)
        self._interval: timedelta | None = self._options.get(CONF_INTERVAL)

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the state is the start of a button hold."""
        event_types = state.attributes.get(EventEntityCapabilityAttribute.EVENT_TYPES)
        if (
            held_event_type := _get_first_declared_event_type(
                event_types, HELD_EVENT_TYPES
            )
        ) is None:
            report_not_triggered(
                "entity_event_types_not_supported",
                entity_id=state.entity_id,
                event_types=event_types,
            )
            return False
        return (
            state.attributes.get(EventEntityStateAttribute.EVENT_TYPE)
            == held_event_type
        )

    def _can_repeat(self, state: State) -> bool:
        """Check if the trigger repeats while the entity stays held."""
        if self._interval is None:
            return False
        event_types = (
            state.attributes.get(EventEntityCapabilityAttribute.EVENT_TYPES) or ()
        )
        # Needs both, to know when the hold ends.
        return (
            ButtonEventType.LONG_PRESS_START in event_types
            and ButtonEventType.LONG_PRESS_END in event_types
        )

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        pending_repeats: dict[str, CALLBACK_TYPE] = {}

        @callback
        def cancel_repeat(entity_id: str) -> None:
            """Stop repeating for an entity."""
            if (cancel := pending_repeats.pop(entity_id, None)) is not None:
                cancel()

        @callback
        def handle_entities_update(
            added: set[str],
            removed: set[str],
            entity_states: Mapping[str, State | None],
        ) -> None:
            """Stop repeating for entities no longer targeted."""
            for entity_id in removed:
                cancel_repeat(entity_id)

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            if from_state and to_state and from_state.state == to_state.state:
                # Attribute only update, not a new event.
                return

            # Any new event, or the entity becoming unavailable, ends the hold.
            cancel_repeat(entity_id)

            if not from_state or not to_state:
                return

            if to_state.state in self._excluded_states:
                return

            @callback
            def report_not_triggered(reason: str, /, **data: Any) -> None:
                """Report why this evaluated change did not fire the trigger."""
                if did_not_trigger is None:
                    return
                did_not_trigger(
                    NotTriggeredInfo(reason=reason, data=data), event.context
                )

            if not self.is_valid_state(to_state, report_not_triggered):
                return

            if from_state.state in self._excluded_from_states:
                return

            @callback
            def call_action(repeat_count: int) -> None:
                """Call action with right context."""
                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                        ATTR_REPEAT_COUNT: repeat_count,
                    },
                    f"state of {entity_id}"
                    if repeat_count == 0
                    else f"hold of {entity_id}",
                    event.context,
                )

            # Monotonic, so a clock change can't shift the repeats or the timeout.
            held_since = self._hass.loop.time()

            @callback
            def held_for() -> timedelta:
                """Return how long the entity has been held."""
                return timedelta(seconds=self._hass.loop.time() - held_since)

            @callback
            def schedule_repeat(repeat_count: int) -> None:
                """Schedule the next repeat, unless it comes after the timeout."""
                if TYPE_CHECKING:
                    assert self._interval is not None
                if held_for() + self._interval >= HOLD_TIMEOUT:
                    return

                @callback
                def fire_repeat(_now: datetime) -> None:
                    """Fire the action again while the entity stays held."""
                    del pending_repeats[entity_id]
                    if held_for() >= HOLD_TIMEOUT:
                        return
                    schedule_repeat(repeat_count + 1)
                    call_action(repeat_count)

                pending_repeats[entity_id] = async_call_later(
                    self._hass, self._interval, fire_repeat
                )

            # Schedule before running the action, so that if the action ends the hold
            # or removes the trigger, the cleanup cancels the scheduled repeat.
            if self._can_repeat(to_state):
                schedule_repeat(1)
            call_action(0)

        unsub = await async_track_target_selector_state_change_event(
            self._hass,
            self._target,
            state_change_listener,
            self.entity_filter,
            handle_entities_update if self._interval else None,
            primary_entities_only=self._primary_entities_only,
        )

        @callback
        def async_remove() -> None:
            """Remove state listeners async."""
            unsub()
            for cancel in pending_repeats.values():
                cancel()
            pending_repeats.clear()

        return async_remove


class ButtonHoldEndedTrigger(StatelessEntityTriggerBase):
    """Trigger for the release of held buttons."""

    _domain_specs = {EVENT_DOMAIN: DomainSpec(device_class=EventDeviceClass.BUTTON)}

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the state is the end of a button hold."""
        event_types = state.attributes.get(EventEntityCapabilityAttribute.EVENT_TYPES)
        # Requires both, as the held trigger fires on long_press_end for entities
        # that don't declare long_press_start.
        if (
            not event_types
            or ButtonEventType.LONG_PRESS_START not in event_types
            or ButtonEventType.LONG_PRESS_END not in event_types
        ):
            report_not_triggered(
                "entity_event_types_not_supported",
                entity_id=state.entity_id,
                event_types=event_types,
            )
            return False
        return (
            state.attributes.get(EventEntityStateAttribute.EVENT_TYPE)
            == ButtonEventType.LONG_PRESS_END
        )


TRIGGERS: dict[str, type[Trigger]] = {
    "pressed": ButtonPressedTrigger,
    "held": ButtonHeldTrigger,
    "hold_ended": ButtonHoldEndedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for buttons."""
    return TRIGGERS
