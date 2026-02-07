"""Timer trigger configuration."""

from collections.abc import Mapping
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import move_top_level_schema_fields_to_options
from homeassistant.helpers.trigger import Trigger, TriggerActionRunner, TriggerConfig
from homeassistant.helpers.typing import ConfigType

from . import (
    EVENT_TIMER_CANCELLED,
    EVENT_TIMER_FINISHED,
    EVENT_TIMER_PAUSED,
    EVENT_TIMER_RESTARTED,
    EVENT_TIMER_STARTED,
)

CONF_EVENTS = "events"

TRIGGER_EVENT_START = "start"
TRIGGER_EVENT_FINISH = "finish"
TRIGGER_EVENT_PAUSE = "pause"
TRIGGER_EVENT_CANCEL = "cancel"
TRIGGER_EVENT_RESTART = "restart"

_LOGGER = logging.getLogger(__name__)

_TRIGGER_EVENT_TIMER_MAP = {
    TRIGGER_EVENT_START: EVENT_TIMER_STARTED,
    TRIGGER_EVENT_FINISH: EVENT_TIMER_FINISHED,
    TRIGGER_EVENT_PAUSE: EVENT_TIMER_PAUSED,
    TRIGGER_EVENT_CANCEL: EVENT_TIMER_CANCELLED,
    TRIGGER_EVENT_RESTART: EVENT_TIMER_RESTARTED,
}

_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    vol.Required(CONF_EVENTS): cv.multi_select(
        [
            TRIGGER_EVENT_START,
            TRIGGER_EVENT_FINISH,
            TRIGGER_EVENT_PAUSE,
            TRIGGER_EVENT_CANCEL,
            TRIGGER_EVENT_RESTART,
        ]
    ),
}

_EVENT_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): vol.All(
            _OPTIONS_SCHEMA_DICT,
        ),
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class TimerEventTrigger(Trigger):
    """Trigger on events."""

    _options: dict[str, Any]
    _target: dict[str, Any]

    @classmethod
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate trigger-specific config."""
        return cast(ConfigType, _EVENT_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)
        assert config.options is not None
        assert config.target is not None
        self._target = config.target
        self._options = config.options
        self._unsubs: list[CALLBACK_TYPE] = []

    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger."""

        tracked_entities = self._target[CONF_ENTITY_ID]

        @callback
        def async_remove() -> None:
            """Remove trigger."""
            for unsub in self._unsubs:
                unsub()

        @callback
        def async_on_event(event: Event) -> None:
            """Handle event."""
            payload = {
                "event_type": event.event_type,
                "data": event.data,
            }
            description = f"Event {event.event_type} detected"
            run_action(payload, description)

        @callback
        def filter_event(data: Mapping[str, str]) -> bool:
            """Filter events that match the configured entity."""
            return data["entity_id"] in tracked_entities

        for track_event in self._options[CONF_EVENTS]:
            event = _TRIGGER_EVENT_TIMER_MAP[track_event]
            unsub = self._hass.bus.async_listen(
                event_type=event,
                event_filter=filter_event,
                listener=async_on_event,
            )
            self._unsubs.append(unsub)

        return async_remove


TRIGGER: dict[str, type[Trigger]] = {
    "events": TimerEventTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return triggers provided by this integration."""
    return TRIGGER
