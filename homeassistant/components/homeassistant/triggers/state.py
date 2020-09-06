"""Offer state listening automation rules."""
from datetime import timedelta
import logging
from typing import Dict, Optional

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.const import CONF_ATTRIBUTE, CONF_FOR, CONF_PLATFORM, MATCH_ALL
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.event import (
    Event,
    async_track_same_state,
    async_track_state_change_event,
    process_state_match,
)

# mypy: allow-incomplete-defs, allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

CONF_ENTITY_ID = "entity_id"
CONF_FROM = "from"
CONF_TO = "to"

TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PLATFORM): "state",
            vol.Required(CONF_ENTITY_ID): cv.entity_ids,
            # These are str on purpose. Want to catch YAML conversions
            vol.Optional(CONF_FROM): vol.Any(str, [str]),
            vol.Optional(CONF_TO): vol.Any(str, [str]),
            vol.Optional(CONF_FOR): cv.positive_time_period_template,
            vol.Optional(CONF_ATTRIBUTE): cv.match_all,
        }
    ),
    cv.key_dependency(CONF_FOR, CONF_TO),
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config,
    action,
    automation_info,
    *,
    platform_type: str = "state",
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    entity_id = config.get(CONF_ENTITY_ID)
    from_state = config.get(CONF_FROM, MATCH_ALL)
    to_state = config.get(CONF_TO, MATCH_ALL)
    time_delta = config.get(CONF_FOR)
    template.attach(hass, time_delta)
    match_all = from_state == MATCH_ALL and to_state == MATCH_ALL
    unsub_track_same = {}
    period: Dict[str, timedelta] = {}
    match_from_state = process_state_match(from_state)
    match_to_state = process_state_match(to_state)
    attribute = config.get(CONF_ATTRIBUTE)

    @callback
    def state_automation_listener(event: Event):
        """Listen for state changes and calls action."""
        entity: str = event.data["entity_id"]
        from_s: Optional[State] = event.data.get("old_state")
        to_s: Optional[State] = event.data.get("new_state")

        if from_s is None:
            old_value = None
        elif attribute is None:
            old_value = from_s.state
        else:
            old_value = from_s.attributes.get(attribute)

        if to_s is None:
            new_value = None
        elif attribute is None:
            new_value = to_s.state
        else:
            new_value = to_s.attributes.get(attribute)

        if (
            not match_from_state(old_value)
            or not match_to_state(new_value)
            or (not match_all and old_value == new_value)
        ):
            return

        @callback
        def call_action():
            """Call action with right context."""
            hass.async_run_job(
                action,
                {
                    "trigger": {
                        "platform": platform_type,
                        "entity_id": entity,
                        "from_state": from_s,
                        "to_state": to_s,
                        "for": time_delta if not time_delta else period[entity],
                        "attribute": attribute,
                        "description": f"state of {entity}",
                    }
                },
                event.context,
            )

        if not time_delta:
            call_action()
            return

        variables = {
            "trigger": {
                "platform": "state",
                "entity_id": entity,
                "from_state": from_s,
                "to_state": to_s,
            }
        }

        try:
            period[entity] = cv.positive_time_period(
                template.render_complex(time_delta, variables)
            )
        except (exceptions.TemplateError, vol.Invalid) as ex:
            _LOGGER.error(
                "Error rendering '%s' for template: %s", automation_info["name"], ex
            )
            return

        def _check_same_state(_, _2, new_st: State):
            if new_st is None:
                return False

            if attribute is None:
                cur_value = new_st.state
            else:
                cur_value = new_st.attributes.get(attribute)

            return cur_value == new_value

        unsub_track_same[entity] = async_track_same_state(
            hass,
            period[entity],
            call_action,
            _check_same_state,
            entity_ids=entity,
        )

    unsub = async_track_state_change_event(hass, entity_id, state_automation_listener)

    @callback
    def async_remove():
        """Remove state listeners async."""
        unsub()
        for async_remove in unsub_track_same.values():
            async_remove()
        unsub_track_same.clear()

    return async_remove
