"""Timer trigger configuration."""

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_TARGET
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import Trigger, TriggerActionRunner, TriggerConfig
from homeassistant.helpers.typing import ConfigType

from . import (
    EVENT_TIMER_CANCELLED,
    EVENT_TIMER_FINISHED,
    EVENT_TIMER_PAUSED,
    EVENT_TIMER_RESTARTED,
    EVENT_TIMER_STARTED,
)

_EVENT_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class BaseTimerEventTrigger(Trigger):
    """Trigger on events."""

    _target: dict[str, Any]
    _event_type: str

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate trigger-specific config."""
        return cast(ConfigType, _EVENT_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)
        assert config.target is not None
        self._target = config.target

    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger."""

        tracked_entities = self._target[CONF_ENTITY_ID]

        @callback
        def async_on_event(event: Event) -> None:
            """Handle event."""
            payload = {
                "event_type": event.event_type,
                "data": event.data,
            }
            description = f"Event {event.event_type} detected"
            run_action(payload, description, context=event.context)

        @callback
        def filter_event(data: Mapping[str, Any]) -> bool:
            """Filter events that match the configured entity."""
            entity_id = data.get("entity_id")
            return isinstance(entity_id, str) and entity_id in tracked_entities

        return self._hass.bus.async_listen(
            event_type=self._event_type,
            event_filter=filter_event,
            listener=async_on_event,
        )


class TimerStartEventTrigger(BaseTimerEventTrigger):
    """Trigger for start event."""

    _event_type = EVENT_TIMER_STARTED


class TimerFinishEventTrigger(BaseTimerEventTrigger):
    """Trigger for finish event."""

    _event_type = EVENT_TIMER_FINISHED


class TimerPauseEventTrigger(BaseTimerEventTrigger):
    """Trigger for pause event."""

    _event_type = EVENT_TIMER_PAUSED


class TimerCancelEventTrigger(BaseTimerEventTrigger):
    """Trigger for cancel event."""

    _event_type = EVENT_TIMER_CANCELLED


class TimerRestartEventTrigger(BaseTimerEventTrigger):
    """Trigger for restart event."""

    _event_type = EVENT_TIMER_RESTARTED


TRIGGERS: dict[str, type[Trigger]] = {
    "started": TimerStartEventTrigger,
    "finished": TimerFinishEventTrigger,
    "paused": TimerPauseEventTrigger,
    "cancelled": TimerCancelEventTrigger,
    "restarted": TimerRestartEventTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return triggers provided by this integration."""
    return TRIGGERS
