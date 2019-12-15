"""Offer state listening automation rules."""
from datetime import timedelta
import logging
from typing import Dict

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.const import CONF_FOR, CONF_PLATFORM, MATCH_ALL
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.event import async_track_same_state, async_track_state_change

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
            vol.Optional(CONF_FOR): vol.Any(
                vol.All(cv.time_period, cv.positive_timedelta),
                cv.template,
                cv.template_complex,
            ),
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

    @callback
    def state_automation_listener(entity, from_s, to_s):
        """Listen for state changes and calls action."""

        @callback
        def call_action():
            """Call action with right context."""
            hass.async_run_job(
                action(
                    {
                        "trigger": {
                            "platform": platform_type,
                            "entity_id": entity,
                            "from_state": from_s,
                            "to_state": to_s,
                            "for": time_delta if not time_delta else period[entity],
                        }
                    },
                    context=to_s.context,
                )
            )

        # Ignore changes to state attributes if from/to is in use
        if (
            not match_all
            and from_s is not None
            and to_s is not None
            and from_s.state == to_s.state
        ):
            return

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
            if isinstance(time_delta, template.Template):
                period[entity] = vol.All(cv.time_period, cv.positive_timedelta)(
                    time_delta.async_render(variables)
                )
            elif isinstance(time_delta, dict):
                time_delta_data = {}
                time_delta_data.update(template.render_complex(time_delta, variables))
                period[entity] = vol.All(cv.time_period, cv.positive_timedelta)(
                    time_delta_data
                )
            else:
                period[entity] = time_delta
        except (exceptions.TemplateError, vol.Invalid) as ex:
            _LOGGER.error(
                "Error rendering '%s' for template: %s", automation_info["name"], ex
            )
            return

        unsub_track_same[entity] = async_track_same_state(
            hass,
            period[entity],
            call_action,
            lambda _, _2, to_state: to_state.state == to_s.state,
            entity_ids=entity,
        )

    unsub = async_track_state_change(
        hass, entity_id, state_automation_listener, from_state, to_state
    )

    @callback
    def async_remove():
        """Remove state listeners async."""
        unsub()
        for async_remove in unsub_track_same.values():
            async_remove()
        unsub_track_same.clear()

    return async_remove
