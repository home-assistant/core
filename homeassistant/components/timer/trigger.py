"""Provides triggers for timers."""

from datetime import datetime, timedelta
from typing import cast, override

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_OPTIONS
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec, filter_by_domain_specs
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.target import (
    TargetStateChangedData,
    async_track_target_selector_state_change_event,
)
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    make_entity_target_state_trigger,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import ATTR_FINISHES_AT, ATTR_LAST_TRANSITION, DOMAIN, STATUS_ACTIVE

CONF_REMAINING = "remaining"

TIME_REMAINING_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_REMAINING): cv.positive_time_period_dict,
        },
    }
)


class TimeRemainingTrigger(Trigger):
    """Trigger when a timer has a specific amount of time remaining."""

    _domain_specs: dict[str, DomainSpec] = {DOMAIN: DomainSpec()}
    _schema = TIME_REMAINING_TRIGGER_SCHEMA

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, cls._schema(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the time remaining trigger."""
        super().__init__(hass, config)
        assert config.target is not None
        self._target = config.target
        options = config.options or {}
        self._remaining: timedelta = options[CONF_REMAINING]

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities to timer domain."""
        return filter_by_domain_specs(self._hass, self._domain_specs, entities)

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        scheduled: dict[str, CALLBACK_TYPE] = {}

        @callback
        def schedule_for_state(
            entity_id: str,
            to_state: State | None,
            context: Context | None,
        ) -> None:
            """Schedule a fire for an active timer state, if applicable."""
            if to_state is None:
                return
            if to_state.state != STATUS_ACTIVE:
                return

            finishes_at_str = to_state.attributes.get(ATTR_FINISHES_AT)
            if finishes_at_str is None:
                return

            finishes_at = dt_util.parse_datetime(finishes_at_str)
            if finishes_at is None:
                return

            fire_at = finishes_at - self._remaining
            if fire_at <= dt_util.utcnow():
                return

            @callback
            def fire_trigger(now: datetime) -> None:
                """Fire the trigger."""
                scheduled.pop(entity_id, None)
                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "to_state": to_state,
                        "remaining": self._remaining,
                    },
                    f"time remaining of {entity_id}",
                    context,
                )

            scheduled[entity_id] = async_track_point_in_utc_time(
                self._hass, fire_trigger, fire_at
            )

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and schedule trigger."""
            event = target_state_change_data.state_change_event
            entity_id: str = event.data["entity_id"]
            to_state = event.data["new_state"]

            # Cancel any previously scheduled callback for this entity
            if entity_id in scheduled:
                scheduled.pop(entity_id)()

            schedule_for_state(entity_id, to_state, event.context)

        @callback
        def on_entities_update(added: set[str], removed: set[str]) -> None:
            """Handle changes to the tracked entity set."""
            for entity_id in removed:
                if entity_id in scheduled:
                    scheduled.pop(entity_id)()
            for entity_id in added:
                state = self._hass.states.get(entity_id)
                schedule_for_state(entity_id, state, state.context if state else None)

        unsub = async_track_target_selector_state_change_event(
            self._hass,
            self._target,
            state_change_listener,
            self.entity_filter,
            on_entities_update,
        )

        @callback
        def async_remove() -> None:
            """Remove state listeners."""
            unsub()
            for cancel in scheduled.values():
                cancel()
            scheduled.clear()

        return async_remove


TRIGGERS: dict[str, type[Trigger]] = {
    "cancelled": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_LAST_TRANSITION)}, "cancelled"
    ),
    "finished": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_LAST_TRANSITION)}, "finished"
    ),
    "paused": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_LAST_TRANSITION)}, "paused"
    ),
    "restarted": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_LAST_TRANSITION)}, "restarted"
    ),
    "started": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_LAST_TRANSITION)}, "started"
    ),
    "time_remaining": TimeRemainingTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for timers."""
    return TRIGGERS
