"""Offer template automation rules."""
import logging

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.const import CONF_FOR, CONF_PLATFORM, CONF_VALUE_TEMPLATE
from homeassistant.core import HassJob, callback
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.event import (
    TrackTemplate,
    async_call_later,
    async_track_template_result,
)
from homeassistant.helpers.template import result_as_boolean

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = IF_ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "template",
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_FOR): cv.positive_time_period_template,
    }
)


async def async_attach_trigger(
    hass, config, action, automation_info, *, platform_type="template"
):
    """Listen for state changes based on configuration."""
    value_template = config.get(CONF_VALUE_TEMPLATE)
    value_template.hass = hass
    time_delta = config.get(CONF_FOR)
    template.attach(hass, time_delta)
    delay_cancel = None
    job = HassJob(action)

    @callback
    def template_listener(event, updates):
        """Listen for state changes and calls action."""
        nonlocal delay_cancel
        result = updates.pop().result

        if delay_cancel:
            # pylint: disable=not-callable
            delay_cancel()
            delay_cancel = None

        if not result_as_boolean(result):
            return

        entity_id = event.data.get("entity_id")
        from_s = event.data.get("old_state")
        to_s = event.data.get("new_state")

        @callback
        def call_action(*_):
            """Call action with right context."""
            hass.async_run_hass_job(
                job,
                {
                    "trigger": {
                        "platform": "template",
                        "entity_id": entity_id,
                        "from_state": from_s,
                        "to_state": to_s,
                        "for": time_delta if not time_delta else period,
                        "description": f"{entity_id} via template",
                    }
                },
                (to_s.context if to_s else None),
            )

        if not time_delta:
            call_action()
            return

        variables = {
            "trigger": {
                "platform": platform_type,
                "entity_id": entity_id,
                "from_state": from_s,
                "to_state": to_s,
            }
        }

        try:
            period = cv.positive_time_period(
                template.render_complex(time_delta, variables)
            )
        except (exceptions.TemplateError, vol.Invalid) as ex:
            _LOGGER.error(
                "Error rendering '%s' for template: %s", automation_info["name"], ex
            )
            return

        delay_cancel = async_call_later(hass, period.seconds, call_action)

    info = async_track_template_result(
        hass,
        [TrackTemplate(value_template, automation_info["variables"])],
        template_listener,
    )
    unsub = info.async_remove

    @callback
    def async_remove():
        """Remove state listeners async."""
        unsub()
        if delay_cancel:
            # pylint: disable=not-callable
            delay_cancel()

    return async_remove
