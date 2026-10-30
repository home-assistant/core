"""Offer numeric state listening automation rules."""

from collections.abc import Callable
from datetime import timedelta
from enum import StrEnum
import logging
from typing import Any

import probatio

from homeassistant import exceptions

# The names marked with noqa are kept for custom integrations,
# and should be deprecated in favour of NumericStateTriggerArgument
from homeassistant.const import (
    CONF_ABOVE,  # noqa: F401
    CONF_ATTRIBUTE,  # noqa: F401
    CONF_BELOW,  # noqa: F401
    CONF_ENTITY_ID,  # noqa: F401
    CONF_FOR,  # noqa: F401
    CONF_PLATFORM,  # noqa: F401
    CONF_VALUE_TEMPLATE,  # noqa: F401
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HassJob,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
    template,
)
from homeassistant.helpers.event import (
    async_track_same_state,
    async_track_state_change_event,
)
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType


class NumericStateTriggerArgument(StrEnum):
    """Store keys for numeric state trigger arguments."""

    ABOVE = "above"
    ATTRIBUTE = "attribute"
    BELOW = "below"
    ENTITY_ID = "entity_id"
    FOR = "for"
    PLATFORM = "platform"
    VALUE_TEMPLATE = "value_template"


def validate_above_below[_T: dict[str, Any]](value: _T) -> _T:
    """Validate that above and below can co-exist."""
    above = value.get(NumericStateTriggerArgument.ABOVE)
    below = value.get(NumericStateTriggerArgument.BELOW)

    if above is None or below is None:
        return value

    if isinstance(above, str) or isinstance(below, str):
        return value

    if above > below:
        raise probatio.Invalid(
            (
                f"A value can never be above {above} and below {below} at the same"
                " time. You probably want two different triggers."
            ),
        )

    return value


_TRIGGER_SCHEMA = probatio.All(
    cv.TRIGGER_BASE_SCHEMA.extend(
        {
            probatio.Required(NumericStateTriggerArgument.PLATFORM): "numeric_state",
            probatio.Required(
                NumericStateTriggerArgument.ENTITY_ID
            ): cv.entity_ids_or_uuids,
            probatio.Optional(
                NumericStateTriggerArgument.BELOW
            ): cv.NUMERIC_STATE_THRESHOLD_SCHEMA,
            probatio.Optional(
                NumericStateTriggerArgument.ABOVE
            ): cv.NUMERIC_STATE_THRESHOLD_SCHEMA,
            probatio.Optional(NumericStateTriggerArgument.VALUE_TEMPLATE): cv.template,
            probatio.Optional(
                NumericStateTriggerArgument.FOR
            ): cv.positive_time_period_template,
            probatio.Optional(NumericStateTriggerArgument.ATTRIBUTE): cv.match_all,
        }
    ),
    probatio.AtLeastOne(
        NumericStateTriggerArgument.BELOW, NumericStateTriggerArgument.ABOVE
    ),
    validate_above_below,
)

_LOGGER = logging.getLogger(__name__)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    config = _TRIGGER_SCHEMA(config)
    registry = er.async_get(hass)
    config[NumericStateTriggerArgument.ENTITY_ID] = er.async_validate_entity_ids(
        registry, cv.entity_ids_or_uuids(config[NumericStateTriggerArgument.ENTITY_ID])
    )
    return config


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
    *,
    platform_type: str = "numeric_state",
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    entity_ids: list[str] = config[NumericStateTriggerArgument.ENTITY_ID]
    below = config.get(NumericStateTriggerArgument.BELOW)
    above = config.get(NumericStateTriggerArgument.ABOVE)
    time_delta = config.get(NumericStateTriggerArgument.FOR)
    value_template = config.get(NumericStateTriggerArgument.VALUE_TEMPLATE)
    unsub_track_same: dict[str, Callable[[], None]] = {}
    armed_entities: set[str] = set()
    period: dict[str, timedelta] = {}
    attribute = config.get(NumericStateTriggerArgument.ATTRIBUTE)
    job = HassJob(action, f"numeric state trigger {trigger_info}")

    trigger_data = trigger_info["trigger_data"]
    _variables = trigger_info["variables"] or {}

    def variables(entity_id: str) -> dict[str, Any]:
        """Return a dict with trigger variables."""
        trigger_info = {
            "trigger": {
                "platform": "numeric_state",
                "entity_id": entity_id,
                "below": below,
                "above": above,
                "attribute": attribute,
            }
        }
        return {**_variables, **trigger_info}

    @callback
    def check_numeric_state(
        entity_id: str, from_s: State | None, to_s: str | State | None
    ) -> bool:
        """Return whether the criteria are met, raise ConditionError if unknown."""
        return condition.async_numeric_state(
            hass, to_s, below, above, value_template, variables(entity_id), attribute
        )

    # Each entity that starts outside the range is already armed (ready to fire).
    for entity_id in entity_ids:
        try:
            if not check_numeric_state(entity_id, None, entity_id):
                armed_entities.add(entity_id)
        except exceptions.ConditionError as ex:
            _LOGGER.warning(
                "Error initializing '%s' trigger: %s",
                trigger_info["name"],
                ex,
            )

    @callback
    def state_automation_listener(event: Event[EventStateChangedData]) -> None:
        """Listen for state changes and calls action."""
        entity_id = event.data["entity_id"]
        from_s = event.data["old_state"]
        to_s = event.data["new_state"]

        if to_s is None:
            return

        @callback
        def call_action() -> None:
            """Call action with right context."""
            hass.async_run_hass_job(
                job,
                {
                    "trigger": {
                        **trigger_data,
                        "platform": platform_type,
                        "entity_id": entity_id,
                        "below": below,
                        "above": above,
                        "from_state": from_s,
                        "to_state": to_s,
                        "for": time_delta if not time_delta else period[entity_id],
                        "description": f"numeric state of {entity_id}",
                    }
                },
                to_s.context,
            )

        @callback
        def check_numeric_state_no_raise(
            entity_id: str, from_s: State | None, to_s: State | None
        ) -> bool:
            """Return True if the criteria are now met, False otherwise."""
            try:
                return check_numeric_state(entity_id, from_s, to_s)
            except exceptions.ConditionError:
                # This is an internal same-state listener so we just drop the
                # error. The same error will be reached and logged by the
                # primary async_track_state_change_event() listener.
                return False

        try:
            matching = check_numeric_state(entity_id, from_s, to_s)
        except exceptions.ConditionError as ex:
            _LOGGER.warning("Error in '%s' trigger: %s", trigger_info["name"], ex)
            return

        if not matching:
            armed_entities.add(entity_id)
        elif entity_id in armed_entities:
            armed_entities.discard(entity_id)

            if time_delta:
                try:
                    period[entity_id] = cv.positive_time_period(
                        template.render_complex(time_delta, variables(entity_id))
                    )
                except (exceptions.TemplateError, probatio.Invalid) as ex:
                    _LOGGER.error(
                        "Error rendering '%s' for template: %s",
                        trigger_info["name"],
                        ex,
                    )
                    return

                unsub_track_same[entity_id] = async_track_same_state(
                    hass,
                    period[entity_id],
                    call_action,
                    entity_ids=entity_id,
                    async_check_same_func=check_numeric_state_no_raise,
                )
            else:
                call_action()

    unsub = async_track_state_change_event(hass, entity_ids, state_automation_listener)

    @callback
    def async_remove() -> None:
        """Remove state listeners async."""
        unsub()
        for async_remove in unsub_track_same.values():
            async_remove()
        unsub_track_same.clear()

    return async_remove
