"""Provides triggers for timer lists."""

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, cast, override

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import TimerListEvent, timer_to_dict
from .const import ATTR_TIMER, DATA_COMPONENT, DOMAIN, TimerListEventType

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
        vol.Required(CONF_OPTIONS, default={}): {},
    }
)


class TimerEventListener(TargetEntityChangeTracker):
    """Subscribe to timer change events for the targeted timer list entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        listener: Callable[[str, TimerListEvent], None],
    ) -> None:
        """Initialize the listener."""

        def entity_filter(entities: set[str]) -> set[str]:
            return {
                entity_id
                for entity_id in entities
                if split_entity_id(entity_id)[0] == DOMAIN
            }

        super().__init__(hass, target_selection, entity_filter)
        self._listener = listener
        self._unsubscribe_listeners: list[CALLBACK_TYPE] = []

    @override
    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Resubscribe when the set of tracked entities changes."""
        for unsub in self._unsubscribe_listeners:
            unsub()
        self._unsubscribe_listeners = []

        component = self._hass.data[DATA_COMPONENT]
        for entity_id in tracked_entities:
            if (entity := component.get_entity(entity_id)) is None:
                continue
            self._unsubscribe_listeners.append(
                entity.async_subscribe_updates(partial(self._listener, entity_id))
            )

    @override
    @callback
    def _unsubscribe(self) -> None:
        """Unsubscribe from all events."""
        super()._unsubscribe()
        for unsub in self._unsubscribe_listeners:
            unsub()
        self._unsubscribe_listeners = []


class TimerEventTrigger(Trigger):
    """Trigger that fires on a specific timer change event type."""

    _event_type: TimerListEventType

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
        self._target = config.target

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        target_selection = TargetSelection(self._target)
        if not target_selection.has_any_target:
            raise HomeAssistantError(f"No target defined in {self._target}")

        @callback
        def handle_event(entity_id: str, event: TimerListEvent) -> None:
            if event.event_type != self._event_type:
                return
            run_action(
                {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_TIMER: timer_to_dict(event.item, dt_util.utcnow()),
                },
                f"timer {self._event_type.value} on {entity_id}",
            )

        listener = TimerEventListener(self._hass, target_selection, handle_event)
        return await listener.async_setup()


class TimerStartedTrigger(TimerEventTrigger):
    """Trigger when a timer starts."""

    _event_type = TimerListEventType.STARTED


class TimerUpdatedTrigger(TimerEventTrigger):
    """Trigger when a timer is paused, resumed, or has time added/removed."""

    _event_type = TimerListEventType.UPDATED


class TimerFinishedTrigger(TimerEventTrigger):
    """Trigger when a timer finishes."""

    _event_type = TimerListEventType.FINISHED


class TimerCancelledTrigger(TimerEventTrigger):
    """Trigger when a timer is cancelled."""

    _event_type = TimerListEventType.CANCELLED


TRIGGERS: dict[str, type[Trigger]] = {
    "timer_started": TimerStartedTrigger,
    "timer_updated": TimerUpdatedTrigger,
    "timer_finished": TimerFinishedTrigger,
    "timer_cancelled": TimerCancelledTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for timer lists."""
    return TRIGGERS
